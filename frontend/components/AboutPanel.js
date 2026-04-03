export default function AboutPanel() {
  return (
    <div className="panel" style={{ height: "600px", overflowY: "auto" }}>
      <h2 style={{ color: "#38bdf8", marginBottom: "20px" }}>About Lecture Intelligence RAG</h2>
      
      <p style={{ color: "#cbd5e1", lineHeight: "1.7", marginBottom: "24px" }}>
        This application is an end-to-end <strong>Retrieval-Augmented Generation (RAG)</strong> system. It bridges the gap between raw video lectures and interactive, AI-driven learning by utilizing a state-of-the-art machine learning pipeline without relying on external third-party closed-source APIs.
      </p>

      <h3 style={{ color: "#a78bfa", marginBottom: "12px", borderBottom: "1px solid #334155", paddingBottom: "8px" }}>The Architecture & Pipeline</h3>
      <ul style={{ color: "#94a3b8", lineHeight: "1.8", marginLeft: "20px", marginBottom: "32px", listStyleType: "circle" }}>
        <li><strong style={{ color: "#f8fafc" }}>1. Extraction & Speech-to-Text:</strong> Audio is extracted from standard YouTube links or MP4 uploads via video parsing algorithms. It is then transcribed locally using the extremely fast <strong>faster-whisper</strong> engine running INT8 quantization (configurable to Medium/Large).</li>
        <li><strong style={{ color: "#f8fafc" }}>2. Tokenization & Splitting:</strong> The raw transcript isn't just blindly chopped by character count. It utilizes a <em>time-aware chunking</em> algorithm that splits the text based on physical audio pauses (thresholds &gt; 1.5 seconds) and character limits (850 max) to ensure that logical sentences aren't cut in half.</li>
        <li><strong style={{ color: "#f8fafc" }}>3. Embeddings:</strong> We utilize <strong>HuggingFace's SentenceTransformers</strong> (specifically the highly efficient `all-MiniLM-L6-v2` architecture) to mathematically embed those discrete contextual chunks into high-density vector space representations.</li>
        <li><strong style={{ color: "#f8fafc" }}>4. Vector Storage:</strong> These document embeddings are persistently stored offline using <strong>ChromaDB</strong>, a robustly optimized Vector Database capable of executing K-Nearest Neighbors mathematical functions at lightning speed.</li>
        <li><strong style={{ color: "#f8fafc" }}>5. Semantic Search:</strong> When you execute a Vector Search or ask the AI Chatbot a question, your query is embedded on-the-fly and routed to ChromaDB to extract the 6 most semantically relevant temporal chunks from the database space.</li>
        <li><strong style={{ color: "#f8fafc" }}>6. Synthesis (LLM):</strong> The retrieved transcript context is carefully injected into a structured Prompt Template and evaluated by a local offline <strong>HuggingFace Large Language Model</strong> running natively on your hardware to synthesize a finalized, intelligently grounded answer.</li>
      </ul>

      <h3 style={{ color: "#34d399", marginBottom: "12px", borderBottom: "1px solid #334155", paddingBottom: "8px" }}>Tech Stack Summary</h3>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "16px", color: "#94a3b8" }}>
        <div style={{ padding: "16px", background: "#1e293b", borderRadius: "8px" }}>
          <strong style={{ color: "#e2e8f0" }}>Backend Server</strong><br/>FastAPI / Python
        </div>
        <div style={{ padding: "16px", background: "#1e293b", borderRadius: "8px" }}>
          <strong style={{ color: "#e2e8f0" }}>Frontend Client</strong><br/>Next.js React Ecosystem
        </div>
        <div style={{ padding: "16px", background: "#1e293b", borderRadius: "8px" }}>
          <strong style={{ color: "#e2e8f0" }}>Vector DB</strong><br/>ChromaDB
        </div>
        <div style={{ padding: "16px", background: "#1e293b", borderRadius: "8px" }}>
          <strong style={{ color: "#e2e8f0" }}>Speech Model</strong><br/>faster-whisper
        </div>
        <div style={{ padding: "16px", background: "#1e293b", borderRadius: "8px" }}>
          <strong style={{ color: "#e2e8f0" }}>LLM Inference Backend</strong><br/>HuggingFace Transformers
        </div>
        <div style={{ padding: "16px", background: "#1e293b", borderRadius: "8px" }}>
          <strong style={{ color: "#e2e8f0" }}>Semantic Visualization</strong><br/>React + CSS Grid Animations
        </div>
      </div>
    </div>
  );
}
