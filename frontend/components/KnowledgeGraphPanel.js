import { useEffect, useState } from "react";
import dynamic from "next/dynamic";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

export default function KnowledgeGraphPanel({ video }) {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadGraph() {
      if (!video?.video_id) return;
      setLoading(true);
      setError("");
      try {
        const res = await fetch(`${API_BASE}/videos/${video.video_id}/graph`);
        if (!res.ok) throw new Error("Failed to load graph");
        const data = await res.json();
        setGraphData(data.graph || { nodes: [], links: [] });
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    loadGraph();
  }, [video?.video_id]);

  if (!video) return (
      <div className="panel" style={{ height: "400px", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <p className="muted">Ingest a lecture to generate the Knowledge Graph.</p>
      </div>
  );

  if (loading) return (
      <div className="panel" style={{ height: "400px", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <p className="muted">Compiling Concept Network...</p>
      </div>
  );

  if (error) return <p style={{ color: "#ff8f8f" }}>{error}</p>;

  if (!graphData.nodes || graphData.nodes.length === 0) {
      return (
          <div className="panel" style={{ height: "400px", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <p className="muted">No knowledge graph data available. LLM extracted empty graph.</p>
          </div>
      );
  }

  return (
    <div className="panel" style={{ padding: 0, overflow: "hidden", display: "flex", height: "600px", backgroundColor: "#0f172a" }}>
      <ForceGraph2D
        graphData={graphData}
        nodeLabel="id"
        nodeColor={(n) => "#818cf8"}
        linkColor={() => "#475569"}
        nodeRelSize={6}
        linkDirectionalArrowLength={3.5}
        linkDirectionalArrowRelPos={1}
        width={800}
        height={600}
      />
    </div>
  );
}
