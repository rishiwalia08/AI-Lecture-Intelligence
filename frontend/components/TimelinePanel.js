import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

function toClock(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

export default function TimelinePanel({ video }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadTimeline() {
      if (!video?.video_id) {
        setItems([]);
        setError("");
        return;
      }

      setLoading(true);
      setError("");
      try {
        const res = await fetch(`${API_BASE}/videos/${video.video_id}/transcript`);
        if (!res.ok) throw new Error("Failed to load timeline");
        const data = await res.json();
        setItems(data.chunks || []);
      } catch (err) {
        setItems([]);
        setError(err.message || "Failed to load timeline");
      } finally {
        setLoading(false);
      }
    }

    loadTimeline();
  }, [video?.video_id]);

  return (
    <div className="panel" style={{ background: "transparent", border: "none", boxShadow: "none", padding: 0 }}>
      {!video && (
        <div className="timeline-container">
            <div className="timeline-row left-side">
                <div className="timeline-center">
                    <div className="timeline-dot"></div>
                    <div className="timeline-time time-right">00:00</div>
                </div>
                <div className="timeline-content">
                    <div className="timeline-card">
                        <h4>Lecture Start</h4>
                        <p>Upload or ingest a lecture to generate real timeline topics.</p>
                    </div>
                </div>
            </div>
             <div className="timeline-row right-side">
                <div className="timeline-center">
                    <div className="timeline-dot"></div>
                    <div className="timeline-time time-left">08:00</div>
                </div>
                <div className="timeline-content">
                    <div className="timeline-card">
                        <h4>Topic Segment</h4>
                        <p>Detected topics will appear here with timestamps after ingestion.</p>
                    </div>
                </div>
            </div>
             <div className="timeline-row left-side">
                <div className="timeline-center">
                    <div className="timeline-dot"></div>
                    <div className="timeline-time time-right">16:00</div>
                </div>
                <div className="timeline-content">
                    <div className="timeline-card">
                        <h4>Examples</h4>
                        <p>Ask questions in chat to jump to relevant moments in the video.</p>
                    </div>
                </div>
            </div>
        </div>
      )}

      {loading && <p className="muted">Building timeline...</p>}
      {error && <p style={{ color: "#ff8f8f" }}>{error}</p>}

      {!loading && !error && video && (
        <div className="timeline-container">
          {items.map((chunk, idx) => {
            const isLeft = idx % 2 === 0;
            return (
              <div className={`timeline-row ${isLeft ? "left-side" : "right-side"}`} key={chunk.chunk_id || idx}>
                <div className="timeline-center">
                  <div className="timeline-dot"></div>
                  <div className={`timeline-time ${isLeft ? "time-right" : "time-left"}`}>
                    {toClock(chunk.start_time)}
                  </div>
                </div>

                <div className="timeline-content">
                  <div className="timeline-card">
                    <h4>{idx === 0 ? "Lecture Start" : `Topic Segment ${idx + 1}`}</h4>
                    <p>{chunk.text.substring(0, 180)}{chunk.text.length > 180 ? "..." : ""}</p>
                    {chunk.youtube_link && (
                      <a href={chunk.youtube_link} target="_blank" rel="noreferrer" className="timeline-link">Jump to video</a>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
