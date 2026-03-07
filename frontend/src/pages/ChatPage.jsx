import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import LoadingDots from '../components/LoadingDots'
import PageTitle from '../components/PageTitle'
import TypingText from '../components/TypingText'
import { useAsk } from '../hooks/useApi'

function formatTimestamp(source) {
  if (source?.timestamp) return source.timestamp
  const seconds = Math.max(0, Number(source?.start_time || 0))
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function ChatPage() {
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hi! I am your AI Lecture Assistant. Ask me anything about your lectures.',
    },
  ])

  const askMutation = useAsk()

  const lastAnswer = useMemo(() => {
    const reversed = [...messages].reverse()
    return reversed.find((m) => m.role === 'assistant' && m.sources)
  }, [messages])

  const onSend = async () => {
    const trimmed = query.trim()
    if (!trimmed || askMutation.isPending) return

    setMessages((prev) => [...prev, { role: 'user', content: trimmed }])
    setQuery('')

    try {
      const data = await askMutation.mutateAsync(trimmed)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.answer || 'No answer returned.',
          sources: data.sources || [],
        },
      ])
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `I hit an error: ${error.message || 'Unknown error'}` },
      ])
    }
  }

  return (
    <section className="flex h-full flex-col">
      <PageTitle title="AI Chat Assistant" subtitle="Ask lecture questions and get grounded answers with timestamps." />

      <div className="scrollbar-thin mb-4 flex-1 space-y-3 overflow-y-auto rounded-2xl border border-slate-700/60 bg-slate-900/35 p-4">
        {messages.map((message, index) => (
          <motion.div
            key={`${message.role}-${index}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
              message.role === 'user'
                ? 'ml-auto bg-indigo-500/30 text-indigo-50 border border-indigo-400/50'
                : 'bg-slate-800/70 text-slate-100 border border-slate-600/70'
            }`}
          >
            {message.role === 'assistant' && index === messages.length - 1 && !askMutation.isPending ? (
              <TypingText text={message.content} />
            ) : (
              message.content
            )}
          </motion.div>
        ))}
        {askMutation.isPending ? <LoadingDots label="AI thinking..." /> : null}
      </div>

      {lastAnswer?.sources?.length ? (
        <div className="mb-4 rounded-2xl border border-slate-600/60 bg-slate-800/35 p-3">
          <p className="mb-2 text-xs uppercase tracking-wider text-slate-300">Sources</p>
          <div className="space-y-2">
            {lastAnswer.sources.slice(0, 3).map((source, i) => (
              <div key={`${source.chunk_id || i}`} className="rounded-xl border border-slate-600/60 bg-slate-900/40 p-3 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="font-medium text-slate-100">{source.lecture_id || 'Lecture'}</p>
                    <p className="text-xs text-slate-300">Timestamp: {formatTimestamp(source)}</p>
                  </div>
                  <button
                    type="button"
                    className="rounded-lg border border-indigo-400/60 bg-indigo-500/20 px-3 py-1 text-xs text-indigo-100 hover:bg-indigo-500/30"
                  >
                    ▶ Play Lecture Segment
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="flex items-center gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              onSend()
            }
          }}
          placeholder="Ask about gradient descent, transformers, backprop..."
          className="w-full rounded-xl border border-slate-600 bg-slate-900/60 px-4 py-3 text-sm text-slate-100 outline-none ring-indigo-400/60 placeholder:text-slate-400 focus:ring"
        />
        <button
          type="button"
          onClick={onSend}
          disabled={askMutation.isPending}
          className="rounded-xl bg-indigo-500 px-5 py-3 text-sm font-semibold text-white transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </section>
  )
}

export default ChatPage
