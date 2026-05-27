import os
import time
import asyncio
from typing import List, Dict, Literal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import cohere

app = FastAPI(title="Enterprise Ticket Triage Pipeline")

# Enable CORS so your React frontend can talk to the backend without issues
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Cohere Client (Ensures CO_API_KEY environment variable is read)
co = cohere.ClientV2()

# --- IN-MEMORY QUEUES ---
# Simulates enterprise message brokers (like RabbitMQ or AWS SQS)
QUEUES: Dict[str, List[Dict]] = {
    "CRITICAL_INFRASTRUCTURE": [],
    "BILLING": [],
    "GENERAL_SUPPORT": []
}

METRICS = {
    "total_processed": 0,
    "pii_redacted_count": 0,
    "avg_latency_ms": 0.0
}

# --- DATA SCHEMAS (CONTRACTS) ---
class RawTicketRequest(BaseModel):
    raw_text: str

# This schema forces Cohere to return structured JSON matching these exact keys
class TriageSchema(BaseModel):
    category: Literal["CRITICAL_INFRASTRUCTURE", "BILLING", "GENERAL_SUPPORT"] = Field(
        description="The primary target department based on system severity."
    )
    urgency: Literal["LOW", "MEDIUM", "HIGH"] = Field(
        description="The operational risk or downtime impact of the ticket."
    )
    sanitized_text: str = Field(
        description="The original text, but names, phone numbers, and emails must be completely replaced with [REDACTED]."
    )
    pii_detected: bool = Field(
        description="True if any PII was identified and scrubbed, otherwise False."
    )

# --- PIPELINE LOGIC WITH RESILIENCY ---
async def process_ticket_through_llm(text: str) -> TriageSchema:
    """Invokes Cohere API with strict JSON schemas and exponential backoff retry logic."""
    max_retries = 3
    delay = 1.0
    
    for attempt in range(max_retries):
        try:
            # We use an async executor wrapper to prevent the synchronous SDK from blocking the event loop
            response = await asyncio.to_thread(
                co.chat,
                model="command-r-plus-08-2024",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a strict, deterministic enterprise ticket routing engine. "
                            "Your primary job is to classify incoming tickets into one of three departments: "
                            "CRITICAL_INFRASTRUCTURE, BILLING, or GENERAL_SUPPORT.\n\n"
                            
                            "CRITICAL ROUTING RULES:\n"
                            "1. BILLING ALWAYS takes precedence over CRITICAL_INFRASTRUCTURE if the root issue "
                            "involves credit cards, invoices, payments, subscriptions, or financial transactions, "
                            "even if technical errors, site crashes, or server bugs are mentioned.\n"
                            "2. CRITICAL_INFRASTRUCTURE is strictly reserved for core system downtime, backend server "
                            "failures, cluster crashes, API performance degradation, or security breaches that do not "
                            "involve user financial accounts.\n"
                            "3. GENERAL_SUPPORT handles routine user management, password resets, UI questions, and how-to guides."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            "Analyze, redact PII, and categorize the following support issues using the examples provided for calibration.\n\n"
                            
                            "--- START CALIBRATION EXAMPLES ---\n"
                            "Example 1:\n"
                            "Input: 'The checkout portal crashed with a 500 internal server error when I entered my Visa card.'\n"
                            "Output: {\"category\": \"BILLING\", \"urgency\": \"HIGH\", \"sanitized_text\": \"The checkout portal crashed with a 500 internal server error when I entered my Visa card.\", \"pii_detected\": false}\n\n"
                            
                            "Example 2:\n"
                            "Input: 'Our production database cluster went offline and API latency spiked by 4000ms.'\n"
                            "Output: {\"category\": \"CRITICAL_INFRASTRUCTURE\", \"urgency\": \"HIGH\", \"sanitized_text\": \"Our production database cluster went offline and API latency spiked by 4000ms.\", \"pii_detected\": false}\n"
                            "--- END CALIBRATION EXAMPLES ---\n\n"
                            
                            f"Now process this live ticket input:\n\n{text}"
                        )
                    }
                ],
                response_format={
                    "type": "json_object",
                    "schema": TriageSchema.model_json_schema()
                }
            )
            
            # Parse the reliable JSON structure returned by Cohere
            return TriageSchema.model_validate_json(response.message.content[0].text)
            
        except Exception as e:
            # Catch transient network errors or rate limits (HTTP 429 / 5xx)
            if "429" in str(e) or "500" in str(e):
                if attempt < max_retries - 1:
                    print(f"[RETRY] Error encountered: {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    delay *= 2  # Exponential backoff
                    continue
            print(f"[ERROR] Pipeline pipeline failed permanently: {e}")
            raise HTTPException(status_code=502, detail=f"Upstream ML Engine failure: {str(e)}")

# --- API ENDPOINTS ---
@app.post("/api/triage")
async def triage_ticket(payload: RawTicketRequest):
    """Ingestion Gateway: Validates, sanitizes, classifies, and routes incoming data."""
    start_time = time.perf_counter()
    
    # 1. Programmatic Input Validation Filter
    cleaned_input = payload.raw_text.strip()
    if len(cleaned_input) < 10:
        raise HTTPException(status_code=400, detail="Input payload fails density check (minimum 10 characters required).")
        
    # 2. Execute Transformation and ML Processing
    triage_result = await process_ticket_through_llm(cleaned_input)
    
    # 3. Calculate Processing Latency
    latency_ms = (time.perf_counter() - start_time) * 1000
    
    # 4. Deterministic Routing Switch
    ticket_id = int(time.time() * 1000)
    routed_record = {
        "id": ticket_id,
        "processed_text": triage_result.sanitized_text,
        "urgency": triage_result.urgency,
        "latency_ms": round(latency_ms, 2)
    }
    
    # Push to correct in-memory queue branch
    QUEUES[triage_result.category].append(routed_record)
    
    # Update global observability metrics
    METRICS["total_processed"] += 1
    if triage_result.pii_detected:
        METRICS["pii_redacted_count"] += 1
    
    # Running average latency calculation
    METRICS["avg_latency_ms"] = ((METRICS["avg_latency_ms"] * (METRICS["total_processed"] - 1)) + latency_ms) / METRICS["total_processed"]
    METRICS["avg_latency_ms"] = round(METRICS["avg_latency_ms"], 2)
    
    return {"status": "routed", "id": ticket_id, "route": triage_result.category}

@app.get("/api/dashboard")
async def get_dashboard_state():
    """Returns current state of all routing queues and hardware-level telemetry metrics."""
    return {
        "queues": QUEUES,
        "metrics": METRICS
    }

if __name__ == "__main__":
    import uvicorn
    # Start server on local port 8000
    uvicorn.run(app, host="127.0.0.1", port=8000)