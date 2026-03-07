import { useMemo } from 'react'
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import * as d3 from 'd3'
import PageTitle from '../components/PageTitle'

function createSyntheticVectors() {
  const query = { x: 0, y: 0, label: 'Query' }
  const nearest = Array.from({ length: 14 }).map((_, i) => {
    const angle = (i / 14) * 2 * Math.PI
    const radius = 0.8 + Math.random() * 1.8
    return {
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius,
      label: `Chunk ${i + 1}`,
    }
  })
  return { query, nearest }
}

function VectorSearchPage() {
  const points = useMemo(createSyntheticVectors, [])

  const hullPath = useMemo(() => {
    const raw = points.nearest.map((d) => [d.x, d.y])
    const hull = d3.polygonHull(raw)
    if (!hull) return null
    return `${hull.map((p) => `${p[0]},${p[1]}`).join(' ')}`
  }, [points])

  return (
    <section>
      <PageTitle title="Vector Search Visualization" subtitle="Inspect query embedding and nearest retrieved vectors." />
      <div className="rounded-2xl border border-slate-700/70 bg-slate-900/40 p-4">
        <div className="h-[420px] w-full">
          <ResponsiveContainer>
            <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 0 }}>
              <CartesianGrid stroke="rgba(148,163,184,0.2)" />
              <XAxis type="number" dataKey="x" stroke="#94a3b8" />
              <YAxis type="number" dataKey="y" stroke="#94a3b8" />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} />
              <Scatter data={points.nearest} fill="#22d3ee" name="Nearest vectors" />
              <Scatter data={[points.query]} fill="#f59e0b" name="Query vector" />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-3 rounded-xl border border-slate-600/60 bg-slate-950/40 p-3 text-xs text-slate-300">
          <p>Nearest vectors are plotted in embedding space; query vector shown in amber.</p>
          {hullPath ? <p className="mt-1 text-slate-400">Cluster hull computed with D3 polygon hull.</p> : null}
        </div>
      </div>
    </section>
  )
}

export default VectorSearchPage
