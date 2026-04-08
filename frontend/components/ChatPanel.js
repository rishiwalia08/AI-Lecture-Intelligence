import { useState } from "react";
import TimestampLinks from "./TimestampLinks";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

export default function ChatPanel({ video }) {
  const [mode, setMode] = useState("qa");

  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [qaLoading, setQaLoading] = useState(false);

  const [query, setQuery] = useState("");
  const [topicResult, setTopicResult] = useState(null);
  const [topicLoading, setTopicLoading] = useState(false);

  async function ask() {
    const userQ = question.trim();
    if (!userQ) return;
    if (userQ.length < 3) {
      setMessages((m) => [...m, { role: "user", text: userQ }, { role: "assistant", text: "Please ask a slightly longer question (at least 3 characters).", refs: [] }]);
      setQuestion("");
      return;
    }
    setQuestion("");
    setMessages((m) => [...m, { role: "user", text: userQ }]);
    setQaLoading(true);

    try {
      const res = await fetch(`${API_BASE}/videos/${video.video_id}/qa`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: userQ }),
      });
      const data = await res.json();
      if (!res.ok) {
        const msg = data?.detail || "Request failed";
        setMessages((m) => [...m, { role: "assistant", text: String(msg), refs: [] }]);
        return;
      }
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: data.answer,
          refs: data.references || [],
          answerType: data.answer_type || "grounded",
          confidence: typeof data.confidence === "number" ? data.confidence : null,
        },
      ]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", text: "Request failed", refs: [] }]);
    } finally {
      setQaLoading(false);
    }
  }

  async function searchTopic() {
    if (!query.trim()) return;
    setTopicLoading(true);
    try {
      const res = await fetch(`${API_BASE}/videos/${video.video_id}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      if (!res.ok) throw new Error("Topic search failed");
      const data = await res.json();
      setTopicResult(data);
    } catch {
      setTopicResult({ explanation: "Request failed", results: [] });
    } finally {
      setTopicLoading(false);
    }
  }

  return (
    <div className="card">
      <div className="sectionHeader">
        <h3>3) AI Chat</h3>
        <span className="muted">Q&A + Topic Search</span>
      </div>

      <div className="tabRow">
        <button type="button" className={`tabBtn ${mode === "qa" ? "active" : ""}`} onClick={() => setMode("qa")}>Q&A</button>
        <button type="button" className={`tabBtn ${mode === "topic" ? "active" : ""}`} onClick={() => setMode("topic")}>Topic Search</button>
      </div>

      {!video ? <p className="muted">Ingest a video first to enable AI chat.</p> : null}

      {mode === "qa" ? (
        <>
          <div className="chatStream">
            {messages.map((m, idx) => (
              <div key={idx} className={`msg ${m.role === "user" ? "user" : "assistant"}`}>
                <div><strong>{m.role === "user" ? "You" : "Assistant"}:</strong> {m.text}</div>
                {m.role === "assistant" ? (
                  <div className="muted" style={{ fontSize: "0.85rem", marginTop: 4 }}>
                    Type: {m.answerType || "grounded"}
                    {typeof m.confidence === "number" ? ` · Confidence: ${Math.round(m.confidence * 100)}%` : ""}
                  </div>
                ) : null}
                {m.role === "assistant" ? <TimestampLinks refs={m.refs} /> : null}
              </div>
            ))}
          </div>
          <div className="row">
            <input
              style={{ flex: 1 }}
              placeholder="Ask about this lecture..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={!video}
            />
            <button type="button" onClick={ask} disabled={!video || qaLoading}>{qaLoading ? "Thinking..." : "Ask"}</button>
          </div>
        </>
      ) : (
        <>
          <div className="row">
            <input
              style={{ flex: 1 }}
              placeholder="Search topic (e.g., gradient descent)"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={!video}
            />
            <button type="button" onClick={searchTopic} disabled={!video || topicLoading}>{topicLoading ? "Searching..." : "Search"}</button>
          </div>
          {topicResult ? (
            <div style={{ marginTop: 12 }}>
              <p>{topicResult.explanation}</p>
              <TimestampLinks refs={topicResult.results || []} />
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
