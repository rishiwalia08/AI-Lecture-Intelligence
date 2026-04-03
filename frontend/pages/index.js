import { useState } from "react";
import Head from "next/head";
import VideoIngestForm from "../components/VideoIngestForm";
import SummaryPanel from "../components/SummaryPanel";
import ChatPanel from "../components/ChatPanel";
import TimelinePanel from "../components/TimelinePanel";
import VectorSearchPanel from "../components/VectorSearchPanel";
import FlashcardsPanel from "../components/FlashcardsPanel";
import AboutPanel from "../components/AboutPanel";
import SystemStatusPanel from "../components/SystemStatusPanel";

const API_BASE = typeof window !== "undefined" ? `${window.location.origin}/api/v1` : "/api/v1";

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState("AI Chat");
  const [video, setVideo] = useState(null);
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState("");

  const TABS = [
    "AI Chat",
    "Timeline",
    "Flashcards",
    "Summaries",
    "Vector Search",
    "System Status",
    "About"
  ];

  async function handleIngested(v) {
    setVideo(v);
    setSummary(null);
    setSummaryError("");
    setSummaryLoading(true);

    try {
      const res = await fetch(`${API_BASE}/videos/${v.video_id}/summary`);
      if (!res.ok) throw new Error("Failed to load summary");
      const data = await res.json();
      setSummary(data.summary);
    } catch (err) {
      setSummaryError(err.message || "Failed to load summary");
    } finally {
      setSummaryLoading(false);
    }
  }

  const renderActiveTab = () => {
    switch (activeTab) {
      case "AI Chat":
        return <ChatPanel video={video} />;
      case "Timeline":
        return <TimelinePanel video={video} />;
      case "Summaries":
        return <SummaryPanel summary={summary} loading={summaryLoading} error={summaryError} />;
      case "Flashcards":
        return <FlashcardsPanel video={video} />;
      case "Vector Search":
        return <VectorSearchPanel video={video} />;
      case "System Status":
        return <SystemStatusPanel />;
      case "About":
        return <AboutPanel />;
      default:
        return null;
    }
  };

  return (
    <>
      <Head>
        <title>Lecture Intelligence Dashboard</title>
      </Head>
      <div className="dashboard-layout">
        <aside className="sidebar">
          <h2>AI Lecture Intelligence</h2>
          <span className="sub-brand">FastAPI + React + Retrieval AI</span>
          
          <div style={{ marginTop: "24px" }}>
            {TABS.map((tab) => (
              <div 
                key={tab} 
                className={`nav-item ${activeTab === tab ? 'active' : ''}`}
                onClick={() => setActiveTab(tab)}
              >
                {tab}
              </div>
            ))}
          </div>
        </aside>
        
        <main className="main-content">
          <h1>{activeTab}</h1>
          <p className="subtitle">
            Modern Speech-RAG Dashboard Workspace
          </p>

          {!video && (
            <div className="panel" style={{ border: "2px solid #3b82f6", background: "#1e3a8a33" }}>
              <h3 style={{color: "#93c5fd"}}>Get Started: Ingest a Lecture</h3>
              <VideoIngestForm onIngested={handleIngested} />
            </div>
          )}

          {video && (
             <div className="panel" style={{ background: "#0f172a", marginBottom: "24px", paddingTop: "12px", paddingBottom: "12px" }}>
              <strong>Active Session:</strong> {video?.title || "No Title"} 
              <span className="muted" style={{marginLeft: "12px", fontSize: "0.85rem"}}>Video ID: {video?.video_id}</span>
             </div>
          )}

          {/* Render Active View */}
          <div className="active-view-container">
            {renderActiveTab()}
          </div>
        </main>
      </div>
    </>
  );
}
