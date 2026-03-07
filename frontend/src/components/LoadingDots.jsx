function LoadingDots({ label = 'AI thinking...' }) {
  return (
    <div className="inline-flex items-center gap-2 rounded-xl border border-indigo-400/40 bg-indigo-500/15 px-3 py-2 text-sm text-indigo-100">
      <span>{label}</span>
      <span className="inline-flex gap-1">
        <span className="h-1.5 w-1.5 animate-pulseDot rounded-full bg-indigo-300" />
        <span className="h-1.5 w-1.5 animate-pulseDot rounded-full bg-indigo-300 [animation-delay:120ms]" />
        <span className="h-1.5 w-1.5 animate-pulseDot rounded-full bg-indigo-300 [animation-delay:240ms]" />
      </span>
    </div>
  )
}

export default LoadingDots
