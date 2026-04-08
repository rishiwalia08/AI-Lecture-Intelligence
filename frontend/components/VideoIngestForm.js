import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

export default function VideoIngestForm({ onIngested }) {
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [title, setTitle] = useState("");
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    const controller = new AbortController();
    let timeoutId;

    try {
      const timeoutMs = 120000;
      timeoutId = setTimeout(() => controller.abort(), timeoutMs);

      const formData = new FormData();
      if (youtubeUrl) formData.append("youtube_url", youtubeUrl);
      if (title) formData.append("title", title);
      if (file) formData.append("file", file);

      const res = await fetch(`${API_BASE}/videos/ingest`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      onIngested(data.video);
    } catch (err) {
      if (err?.name === "AbortError") {
        setError("Ingestion is taking too long (over 2 minutes). Try a shorter video, use a normal watch URL with captions, or upload the video file directly.");
      } else {
        setError(err.message || "Failed to ingest video");
      }
    } finally {
      if (timeoutId) clearTimeout(timeoutId);
      setLoading(false);
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <div className="sectionHeader">
        <h3>1) Ingest Lecture</h3>
        <span className="muted">YouTube URL or local upload</span>
      </div>

      <div className="row">
        <div className="field" style={{ flex: 1 }}>
          <label>YouTube URL</label>
          <input
            placeholder="https://youtube.com/..."
            value={youtubeUrl}
            onChange={(e) => setYoutubeUrl(e.target.value)}
          />
        </div>
        <div className="field" style={{ flex: 1 }}>
          <label>Title (optional)</label>
          <input
            placeholder="ML Lecture #4"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>
      </div>

      <div className="field" style={{ marginTop: 12 }}>
        <label>Upload file (optional)</label>
        <input type="file" accept="video/*" onChange={(e) => setFile(e.target.files?.[0] || null)} />
      </div>

      <div style={{ marginTop: 12 }}>
        <button disabled={loading}>{loading ? "Processing..." : "Ingest + Generate Summary"}</button>
      </div>
      {error ? <p style={{ color: "#ff8f8f" }}>{error}</p> : null}
    </form>
  );
}
