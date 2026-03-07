import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import Sidebar from './Sidebar'
import ThemeToggle from './ThemeToggle'

function AppShell({ children }) {
  const [dark, setDark] = useState(true)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
  }, [dark])

  return (
    <div className="min-h-screen bg-brand-bg p-4 text-slate-100 md:p-6">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-4 md:grid-cols-[260px_1fr]">
        <Sidebar />
        <motion.main
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="space-y-4"
        >
          <header className="glass flex items-center justify-between rounded-2xl px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-100">AI Lecture Intelligence</h2>
              <p className="text-xs text-slate-300">FastAPI + React + Retrieval AI</p>
            </div>
            <ThemeToggle dark={dark} onToggle={() => setDark((v) => !v)} />
          </header>
          <div className="glass min-h-[78vh] rounded-2xl p-4 md:p-6">{children}</div>
        </motion.main>
      </div>
    </div>
  )
}

export default AppShell
