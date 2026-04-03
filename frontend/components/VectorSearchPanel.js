import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE;

export default function VectorSearchPanel({ video }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [explanation, setExplanation] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim() || !video?.video_id) return;

    setLoading(true);
    setError("");
    setResults([]);
    setExplanation("");

    try {
      const res = await fetch(`${API_BASE}/videos/${video.video_id}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });

      if (!res.ok) throw new Error("Search failed.");
      
      const data = await res.json();
      setExplanation(data.explanation || "");
      setResults(data.results || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (!video) {
    return <div className="panel"><p className="muted">Ingest a lecture to use semantic search.</p></div>;
  }

  return (
    <div className="panel" style={{ display: "flex", flexDirection: "column", height: "600px" }}>
      <h3 style={{ marginBottom: "16px", color: "#38bdf8" }}>Vector Database Search</h3>
      <p className="muted" style={{ marginBottom: "20px" }}>
        Perform a semantic similarity search across ChromaDB embeddings to find precise moments and quotes from the video.
      </p>

      <form onSubmit={handleSearch} style={{ display: "flex", gap: "10px", marginBottom: "24px" }}>
        <input
          className="chat-input"
          style={{ flex: 1, padding: "12px 16px" }}
          type="text"
          placeholder="e.g. When did they talk about..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="submit" disabled={loading} style={{ padding: "12px 24px" }}>
          {loading ? "Searching..." : "Search"}
        </button>
      </form>

      {error && <p style={{ color: "#ff8f8f", marginBottom: "16px" }}>{error}</p>}
      
      {explanation && <p style={{ color: "#c4b5fd", marginBottom: "16px", fontWeight: "bold" }}>{explanation}</p>}

      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "16px", paddingRight: "8px" }}>
        {results.map((ref, idx) => (
          <div key={idx} style={{ padding: "16px", backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
              <span style={{ color: "#34d399", fontWeight: "600", fontSize: "0.9rem" }}>{ref.timestamp}</span>
              {ref.youtube_link && (
                <a href={ref.youtube_link} target="_blank" rel="noreferrer" style={{ color: "#818cf8", fontSize: "0.85rem", textDecoration: "none", textTransform: "uppercase" }}>
                  Watch Video &rarr;
                </a>
              )}
            </div>
            <p style={{ color: "#e2e8f0", lineHeight: "1.6" }}>"{ref.text}"</p>
          </div>
        ))}
        {results.length === 0 && !loading && explanation && (
            <p className="muted">Try another phrase.</p>
        )}
      </div>
    </div>
  );
}
