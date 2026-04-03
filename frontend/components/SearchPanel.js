import { useState } from "react";
import TimestampLinks from "./TimestampLinks";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE;

export default function SearchPanel({ video }) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  async function search() {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/videos/${video.video_id}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const data = await res.json();
      setResult(data);
    } finally {
      setLoading(false);
    }
  }

  if (!video) return null;

  return (
    <div className="card">
      <h3>4) Topic Search</h3>
      <div className="row">
        <input
          style={{ flex: 1 }}
          placeholder="Search topic (e.g., gradient descent)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button onClick={search} disabled={loading}>{loading ? "Searching..." : "Search"}</button>
      </div>
      {result ? (
        <div style={{ marginTop: 12 }}>
          <p>{result.explanation}</p>
          <TimestampLinks refs={result.results || []} />
        </div>
      ) : null}
    </div>
  );
}
