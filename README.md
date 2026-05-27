# Transactional Ticket Triage (TTT)

Telemetry & Ticket Triage (TTT) is a high-performance, full-stack enterprise data pipeline designed to safely ingest, sanitize, and deterministically route unstructured customer support payloads. Built with a FastAPI backend and a React/JavaScript frontend, the system acts as an automated triage gatekeeper that processes untrusted text streams through an advanced machine learning layer powered by Cohere.

The core runtime pipeline enforces strict engineering guardrails by combining asynchronous data execution with automated data hygiene. Upon ingestion, the system utilizes Cohere's language models constrained by strict Pydantic JSON schemas to securely detect and redact Personally Identifiable Information (PII) while simultaneously classifying the ticket's domain and operational urgency. To ensure system reliability under heavy volume, the backend implements client-side exponential backoff loops to gracefully handle transient network errors or rate limits, routing the validated, structured payloads into target in-memory priority queues visualized in real-time on a telemetry dashboard.

Frontend: React(JS)/Vite, Backend: Python with FastAPI, Model: Cohere ClientV2 SDK (command-r-plus-08-2024)
