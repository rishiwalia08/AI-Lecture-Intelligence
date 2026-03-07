import PageTitle from '../components/PageTitle'
import KnowledgeGraphCanvas from '../components/KnowledgeGraphCanvas'
import LoadingDots from '../components/LoadingDots'
import { useKnowledgeGraph } from '../hooks/useApi'

function GraphPage() {
  const { data, isLoading, isError, error } = useKnowledgeGraph()

  return (
    <section>
      <PageTitle title="Concept Knowledge Graph" subtitle="Explore concepts and relationships with interactive D3 visualization." />
      {isLoading ? <LoadingDots label="Loading graph..." /> : null}
      {isError ? (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-rose-100">
          Failed to load graph: {error.message}
        </div>
      ) : null}
      {data?.nodes?.length ? (
        <KnowledgeGraphCanvas data={data} />
      ) : !isLoading ? (
        <div className="rounded-xl border border-slate-700 bg-slate-900/30 p-4 text-sm text-slate-300">
          No graph data available. Generate knowledge graph using backend pipeline.
        </div>
      ) : null}
    </section>
  )
}

export default GraphPage
