import { motion } from 'framer-motion'
import PageTitle from '../components/PageTitle'

function AboutPage() {
  return (
    <section>
      <PageTitle title="About Project" subtitle="System architecture and technology overview." />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <motion.div layout className="glass rounded-2xl border border-slate-700/60 p-4">
          <p className="mb-3 text-sm font-semibold text-white">Architecture</p>
          <div className="rounded-xl border border-indigo-400/35 bg-slate-950/45 p-4 text-sm text-slate-200">
            <p className="font-mono text-indigo-200">Speech → Retrieval → LLM → Answer</p>
            <div className="mt-3 space-y-2 text-slate-300">
              <p>1. Whisper ASR transcribes lecture audio</p>
              <p>2. Hybrid retrieval finds relevant chunks</p>
              <p>3. LLM generates grounded response</p>
              <p>4. UI displays answer with citations + timestamps</p>
            </div>
          </div>
        </motion.div>

        <motion.div layout className="glass rounded-2xl border border-slate-700/60 p-4">
          <p className="mb-3 text-sm font-semibold text-white">Tech Stack</p>
          <ul className="space-y-2 text-sm text-slate-300">
            <li>Frontend: React, TailwindCSS, Framer Motion</li>
            <li>Data UX: React Query, Recharts, D3.js</li>
            <li>Backend: FastAPI + Speech-RAG</li>
            <li>LLM: Hugging Face Inference API</li>
            <li>Vector Store: ChromaDB</li>
          </ul>
        </motion.div>
      </div>
    </section>
  )
}

export default AboutPage
