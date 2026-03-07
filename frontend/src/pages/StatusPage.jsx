import KpiCard from '../components/KpiCard'
import LoadingDots from '../components/LoadingDots'
import PageTitle from '../components/PageTitle'
import { useHealth, useKnowledgeGraph } from '../hooks/useApi'

function StatusPage() {
  const { data: health, isLoading: healthLoading } = useHealth()
  const { data: graph, isLoading: graphLoading } = useKnowledgeGraph()

  const metrics = {
    lectures: graph?.meta?.lecture_count ?? '—',
    transcriptSegments: graph?.nodes?.length ?? '—',
    vectorDbSize: graph?.edges?.length ?? '—',
    llmProvider: 'huggingface',
  }

  return (
    <section>
      <PageTitle title="System Status" subtitle="Live operational metrics for your AI lecture stack." />
      {healthLoading || graphLoading ? <LoadingDots label="Refreshing metrics..." /> : null}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Number of lectures" value={metrics.lectures} icon="🎓" />
        <KpiCard label="Transcript segments" value={metrics.transcriptSegments} icon="🧩" />
        <KpiCard label="Vector database size" value={metrics.vectorDbSize} icon="🗃️" />
        <KpiCard label="LLM provider" value={metrics.llmProvider} icon="🧠" />
      </div>

      <div className="mt-4 rounded-2xl border border-slate-700/60 bg-slate-900/35 p-4 text-sm">
        <p className="text-slate-300">API Status: <span className="font-semibold text-emerald-300">{health?.status || 'unknown'}</span></p>
        <p className="mt-1 text-slate-300">RAG Ready: <span className="font-semibold text-indigo-200">{String(health?.rag_ready ?? false)}</span></p>
        <p className="mt-1 text-slate-400">{health?.message || 'No status message available.'}</p>
      </div>
    </section>
  )
}

export default StatusPage
