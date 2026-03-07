function ThemeToggle({ dark, onToggle }) {
  return (
    <button
      onClick={onToggle}
      className="rounded-xl border border-slate-600 bg-slate-800/60 px-3 py-2 text-xs text-slate-100 transition hover:border-indigo-400"
      type="button"
    >
      {dark ? '🌙 Dark' : '☀️ Light'}
    </button>
  )
}

export default ThemeToggle
