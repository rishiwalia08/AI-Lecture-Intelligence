import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE;

export default function FlashcardsPanel({ video }) {
  const [flashcards, setFlashcards] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);

  useEffect(() => {
    async function loadFlashcards() {
      if (!video?.video_id) return;
      setLoading(true);
      setError("");
      try {
        const res = await fetch(`${API_BASE}/videos/${video.video_id}/flashcards`);
        if (!res.ok) throw new Error("Failed to load flashcards");
        const data = await res.json();
        setFlashcards(data.flashcards || []);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    loadFlashcards();
  }, [video?.video_id]);

  if (!video) return <div className="panel"><p className="muted">Ingest a lecture to generate flashcards.</p></div>;
  if (loading) return <div className="panel"><p className="muted">AI is generating your spaced-repetition deck...</p></div>;
  if (error) return <div className="panel"><p style={{ color: "#ff8f8f" }}>{error}</p></div>;
  if (flashcards.length === 0) return <div className="panel"><p className="muted">No flashcards found. Check logs.</p></div>;

  const currentCard = flashcards[currentIndex];

  const handleNext = () => {
    setFlipped(false);
    setCurrentIndex((prev) => (prev + 1) % flashcards.length);
  };

  const handlePrev = () => {
    setFlipped(false);
    setCurrentIndex((prev) => (prev - 1 + flashcards.length) % flashcards.length);
  };

  return (
    <div className="panel" style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
      <h3 style={{ marginBottom: "20px" }}>Review Deck ({currentIndex + 1} / {flashcards.length})</h3>
      
      <div 
        onClick={() => setFlipped(!flipped)}
        style={{
          width: "100%",
          maxWidth: "700px",
          height: "450px",
          perspective: "1000px",
          cursor: "pointer",
          marginBottom: "24px"
        }}
      >
        <div style={{
          position: "relative",
          width: "100%",
          height: "100%",
          textAlign: "center",
          transition: "transform 0.6s",
          transformStyle: "preserve-3d",
          transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)"
        }}>
          {/* Front */}
          <div style={{
            position: "absolute",
            width: "100%",
            height: "100%",
            backfaceVisibility: "hidden",
            backgroundColor: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "12px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "flex-start",
            padding: "32px",
            boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.5)",
            overflowY: "auto"
          }}>
            <span style={{ color: "#38bdf8", fontSize: "0.9rem", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "16px" }}>Concept</span>
            <h2 style={{ color: "#f8fafc", fontSize: "1.8rem" }}>{currentCard?.front}</h2>
            <p className="muted" style={{ marginTop: "auto", fontSize: "0.85rem" }}>Click to reveal</p>
          </div>
          
          {/* Back */}
          <div style={{
            position: "absolute",
            width: "100%",
            height: "100%",
            backfaceVisibility: "hidden",
            backgroundColor: "#2e1065",
            border: "1px solid #4c1d95",
            borderRadius: "12px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "flex-start",
            padding: "32px",
            transform: "rotateY(180deg)",
            boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.5)",
            overflowY: "auto"
          }}>
            <span style={{ color: "#c4b5fd", fontSize: "0.9rem", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "16px", flexShrink: 0 }}>Definition</span>
            <p style={{ color: "#f8fafc", fontSize: "1.05rem", lineHeight: "1.7", textAlign: "left", width: "100%" }}>{currentCard?.back}</p>
          </div>
        </div>
      </div>

      <div style={{ display: "flex", gap: "16px" }}>
        <button onClick={handlePrev} style={{ backgroundColor: "#334155" }}>&larr; Previous</button>
        <button onClick={handleNext} style={{ backgroundColor: "#334155" }}>Next &rarr;</button>
      </div>
    </div>
  );
}
