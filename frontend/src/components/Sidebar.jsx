import { NavLink } from 'react-router-dom'

const navItems = [
  { to: '/', label: 'AI Chat' },
  { to: '/timeline', label: 'Timeline' },
  { to: '/graph', label: 'Knowledge Graph' },
  { to: '/flashcards', label: 'Flashcards' },
  { to: '/summaries', label: 'Summaries' },
  { to: '/vectors', label: 'Vector Search' },
  { to: '/status', label: 'System Status' },
  { to: '/about', label: 'About' },
]

function Sidebar() {
  return (
    <aside className="glass h-full rounded-2xl p-4 md:p-5">
      <div className="mb-6">
        <h1 className="text-lg font-semibold text-white">AI Lecture Intelligence</h1>
        <p className="mt-1 text-xs text-slate-300">Modern Speech-RAG Dashboard</p>
      </div>
      <nav className="space-y-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `block rounded-xl px-3 py-2 text-sm transition ${
                isActive
                  ? 'bg-indigo-500/30 text-indigo-100 border border-indigo-400/50'
                  : 'text-slate-300 hover:bg-slate-700/40 hover:text-white border border-transparent'
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}

export default Sidebar
