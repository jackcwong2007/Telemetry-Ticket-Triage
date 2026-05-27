import React, { useState, useEffect } from 'react';

interface Ticket {
  id: number;
  processed_text: string;
  urgency: string;
  latency_ms: number;
}

interface DashboardState {
  queues: { [key: string]: Ticket[] };
  metrics: {
    total_processed: number;
    pii_redacted_count: number;
    avg_latency_ms: number;
  };
}

export default function App() {
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<DashboardState>({
    queues: { CRITICAL_INFRASTRUCTURE: [], BILLING: [], GENERAL_SUPPORT: [] },
    metrics: { total_processed: 0, pii_redacted_count: 0, avg_latency_ms: 0 }
  });

  const fetchState = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/dashboard');
      const state = await res.json();
      setData(state);
    } catch (err) {
      console.error("Failed to sync dashboard state.", err);
    }
  };

  useEffect(() => {
    fetchState();
  }, []);

  const handleRouteTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    setLoading(true);

    try {
      await fetch('http://127.0.0.1:8000/api/triage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_text: inputText }),
      });
      setInputText('');
      await fetchState(); // Instantly sync state UI upon successful route
    } catch (err) {
      alert("Error transmitting packet to core pipeline.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '24px', fontFamily: 'monospace', color: '#1a1a1a', maxWidth: '1400px', margin: '0 auto' }}>
      <header style={{ borderBottom: '2px solid #1a1a1a', paddingBottom: '12px', marginBottom: '24px' }}>
        <h1 style={{ margin: 0, fontSize: '24px' }}>OPERATIONAL TRIAGE & BACKEND ROUTING GATEWAY</h1>
      </header>

      {/* SYSTEM METRICS STATUS BAR */}
      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '24px', background: '#f5f5f5', padding: '16px', border: '1px solid #ddd' }}>
        <div><strong>TOTAL PIPELINE VOLUME:</strong> {data.metrics.total_processed} packets</div>
        <div><strong>PII INTERCEPTIONS:</strong> {data.metrics.pii_redacted_count} incidents</div>
        <div><strong>AVG PIPELINE LATENCY:</strong> {data.metrics.avg_latency_ms} ms</div>
      </section>

      {/* INPUT WORKSPACE */}
      <section style={{ marginBottom: '32px' }}>
        <form onSubmit={handleRouteTicket}>
          <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '8px' }}>INGEST NEW UNTRUSTED TEXT STREAM:</label>
          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Paste text containing routing signals or sensitive info (e.g., 'My name is Alice Smith. The cloud cluster crashed with a segmentation fault...')"
            style={{ width: '100%', height: '100px', padding: '12px', boxSizing: 'border-box', marginBottom: '12px', fontSize: '14px' }}
          />
          <button type="submit" disabled={loading} style={{ background: '#1a1a1a', color: '#fff', border: 'none', padding: '10px 20px', cursor: 'pointer', fontWeight: 'bold' }}>
            {loading ? 'PROCESSING THROUGH ENGINE...' : 'EXECUTE RUNTIME TRIAGE'}
          </button>
        </form>
      </section>

      {/* DETERMINISTIC QUEUES KANBAN INTERFACE */}
      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px' }}>
        {Object.keys(data.queues).map((queueName) => (
          <div key={queueName} style={{ border: '2px solid #1a1a1a', borderRadius: '4px', background: '#fff' }}>
            <div style={{ background: '#1a1a1a', color: '#fff', padding: '10px', fontWeight: 'bold', fontSize: '14px' }}>
              {queueName} ({data.queues[queueName].length})
            </div>
            <div style={{ padding: '12px', minHeight: '300px', maxHeight: '500px', overflowY: 'auto' }}>
              {data.queues[queueName].length === 0 ? (
                <div style={{ color: '#888', fontStyle: 'italic', textAlign: 'center', marginTop: '40px' }}>Queue Empty</div>
              ) : (
                data.queues[queueName].map((ticket) => (
                  <div key={ticket.id} style={{ border: '1px solid #ccc', padding: '12px', marginBottom: '12px', borderRadius: '4px', background: '#fafafa' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '12px', color: '#666' }}>
                      <span>ID: {ticket.id}</span>
                      <span style={{ fontWeight: 'bold', color: ticket.urgency === 'HIGH' ? '#d9534f' : '#f0ad4e' }}>
                        [{ticket.urgency}]
                      </span>
                    </div>
                    <p style={{ margin: '0 0 8px 0', fontSize: '13px', lineHeight: '1.4' }}>{ticket.processed_text}</p>
                    <div style={{ fontSize: '11px', color: '#999', textAlign: 'right' }}>
                      Execution: {ticket.latency_ms} ms
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}