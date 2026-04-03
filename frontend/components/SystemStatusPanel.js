export default function SystemStatusPanel() {
  return (
    <div className="panel">
      <h3 style={{ color: "#38bdf8", marginBottom: "16px" }}>System Diagnostic Status</h3>
      <p className="muted" style={{ marginBottom: "24px" }}>
        Live telemetry for local data storage and machine learning services powering the RAG pipeline.
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        <div style={{ padding: "16px", background: "#1e293b", borderRadius: "8px", borderLeft: "4px solid #10b981", display: "flex", justifyContent: "space-between" }}>
          <div>
            <strong style={{ color: "#e2e8f0", display: "block", marginBottom: "4px" }}>FastAPI Backend</strong>
            <span style={{ color: "#94a3b8", fontSize: "0.9rem" }}>Core application router & LLM orchestrator.</span>
          </div>
          <span style={{ color: "#10b981", fontWeight: "bold" }}>Listening (8000)</span>
        </div>

        <div style={{ padding: "16px", background: "#1e293b", borderRadius: "8px", borderLeft: "4px solid #10b981", display: "flex", justifyContent: "space-between" }}>
          <div>
            <strong style={{ color: "#e2e8f0", display: "block", marginBottom: "4px" }}>ChromaDB</strong>
            <span style={{ color: "#94a3b8", fontSize: "0.9rem" }}>Persistent multidimensional vector database array.</span>
          </div>
          <span style={{ color: "#10b981", fontWeight: "bold" }}>Online</span>
        </div>

        <div style={{ padding: "16px", background: "#1e293b", borderRadius: "8px", borderLeft: "4px solid #3b82f6", display: "flex", justifyContent: "space-between" }}>
          <div>
            <strong style={{ color: "#e2e8f0", display: "block", marginBottom: "4px" }}>JSON Artifact Store</strong>
            <span style={{ color: "#94a3b8", fontSize: "0.9rem" }}>Local caching engine for parsed components (Summaries/Flashcards).</span>
          </div>
          <span style={{ color: "#3b82f6", fontWeight: "bold" }}>Healthy</span>
        </div>

        <div style={{ padding: "16px", background: "#1e293b", borderRadius: "8px", borderLeft: "4px solid #f59e0b", display: "flex", justifyContent: "space-between" }}>
          <div>
            <strong style={{ color: "#e2e8f0", display: "block", marginBottom: "4px" }}>HuggingFace AI Pipeline</strong>
            <span style={{ color: "#94a3b8", fontSize: "0.9rem" }}>TensorFlow/PyTorch execution layer for ASR, Embeddings, and Generation.</span>
          </div>
          <span style={{ color: "#f59e0b", fontWeight: "bold" }}>Standby</span>
        </div>
      </div>
    </div>
  );
}
