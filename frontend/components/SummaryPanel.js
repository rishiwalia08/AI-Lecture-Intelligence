export default function SummaryPanel({ summary, loading, error }) {
  return (
    <div className="panel" style={{ background: "transparent", border: "none", boxShadow: "none", padding: 0 }}>
      {loading && <p className="muted">Generating summary...</p>}
      {error && <p style={{ color: "#ff8f8f" }}>{error}</p>}

      {!summary && !loading && !error && (
        <div style={{ padding: "0" }}>
            <p className="muted" style={{ marginTop: "20px" }}>Ingest a video to generate an AI summary.</p>
        </div>
      )}

      {summary && (
        <>
          <div className="panel" style={{ marginBottom: "16px", backgroundColor: "#1e293b" }}>
            <h3 style={{ color: "#38bdf8", marginBottom: "8px" }}>TL;DR</h3>
            {summary.tldr ? summary.tldr.split('\n').map((line, i) => (
               <p key={i} style={{ marginBottom: line.trim() ? "8px" : "0", color: "#e2e8f0", lineHeight: "1.6" }}>
                 {line}
               </p>
            )) : "—"}
          </div>

          <div className="panel" style={{ marginBottom: "16px", backgroundColor: "#1e293b" }}>
            <h3 style={{ color: "#a78bfa", marginBottom: "8px" }}>Detailed Notes</h3>
            <div style={{ color: "#94a3b8", lineHeight: "1.7" }}>
              {summary.detailed_notes ? summary.detailed_notes.split('\n').map((line, i) => (
                 <p key={i} style={{ marginBottom: line.trim() ? "12px" : "0", minHeight: line.trim() ? "auto" : "8px" }}>
                   {line}
                 </p>
              )) : "—"}
            </div>
          </div>

          <div className="panel" style={{ backgroundColor: "#1e293b" }}>
            <h3 style={{ color: "#34d399", marginBottom: "12px" }}>Key Points</h3>
            <ul style={{ paddingLeft: "20px", color: "#94a3b8", lineHeight: "1.7" }}>
              {(summary.key_points || []).map((k, i) => <li key={i} style={{ marginBottom: "8px" }}>{k}</li>)}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
