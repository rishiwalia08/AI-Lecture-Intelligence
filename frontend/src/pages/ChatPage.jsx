import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import LoadingDots from '../components/LoadingDots'
import PageTitle from '../components/PageTitle'
import TypingText from '../components/TypingText'
import { useAsk, useIngestVideo, useIngestYoutube } from '../hooks/useApi'

function formatTimestamp(source) {
  if (source?.timestamp) return source.timestamp
  const seconds = Math.max(0, Number(source?.start_time || 0))
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function ChatPage() {
  const [query, setQuery] = useState('')
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [lectureId, setLectureId] = useState('')
  const [selectedFile, setSelectedFile] = useState(null)
  const [ingestMessage, setIngestMessage] = useState('')
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hi! I am your AI Lecture Assistant. Ask me anything about your lectures.',
    },
  ])

  const askMutation = useAsk()
  const ingestYoutubeMutation = useIngestYoutube()
  const ingestVideoMutation = useIngestVideo()

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

  const onIngestYoutube = async () => {
    const url = youtubeUrl.trim()
    if (!url || ingestYoutubeMutation.isPending) return
    setIngestMessage('Ingesting YouTube video. This can take a few minutes...')
    try {
      const result = await ingestYoutubeMutation.mutateAsync({ url, lectureId })
      setIngestMessage(`✅ Ingested ${result.lecture_id} (${result.num_chunks} chunks indexed)`)
      setYoutubeUrl('')
    } catch (error) {
      setIngestMessage(`❌ ${error.message || 'Failed to ingest YouTube video.'}`)
    }
  }

  const onIngestFile = async () => {
    if (!selectedFile || ingestVideoMutation.isPending) return
    setIngestMessage('Uploading and processing media file...')
    try {
      const result = await ingestVideoMutation.mutateAsync({ file: selectedFile, lectureId })
      setIngestMessage(`✅ Ingested ${result.lecture_id} (${result.num_chunks} chunks indexed)`)
      setSelectedFile(null)
    } catch (error) {
      setIngestMessage(`❌ ${error.message || 'Failed to ingest file.'}`)
    }
  }

  return (
    <section className="flex h-full flex-col">
      <PageTitle title="AI Chat Assistant" subtitle="Ask lecture questions and get grounded answers with timestamps." />

      <div className="mb-4 rounded-2xl border border-slate-600/60 bg-slate-900/40 p-3">
        <p className="mb-2 text-xs uppercase tracking-wider text-slate-300">Ingest Lecture Content</p>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
          <input
            value={youtubeUrl}
            onChange={(e) => setYoutubeUrl(e.target.value)}
            placeholder="Paste YouTube link"
            className="rounded-lg border border-slate-600 bg-slate-900/70 px-3 py-2 text-sm text-slate-100 outline-none focus:ring-1 focus:ring-indigo-400"
          />
          <input
            value={lectureId}
            onChange={(e) => setLectureId(e.target.value)}
            placeholder="Optional lecture id"
            className="rounded-lg border border-slate-600 bg-slate-900/70 px-3 py-2 text-sm text-slate-100 outline-none focus:ring-1 focus:ring-indigo-400"
          />
          <button
            type="button"
            onClick={onIngestYoutube}
            disabled={ingestYoutubeMutation.isPending}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            Ingest YouTube
          </button>
        </div>
        <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-3">
          <input
            type="file"
            accept="video/*,audio/*"
            onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
            className="rounded-lg border border-slate-600 bg-slate-900/70 px-3 py-2 text-sm text-slate-200"
          />
          <div className="md:col-span-2">
            <button
              type="button"
              onClick={onIngestFile}
              disabled={!selectedFile || ingestVideoMutation.isPending}
              className="w-full rounded-lg bg-teal-600 px-3 py-2 text-sm font-semibold text-white hover:bg-teal-500 disabled:opacity-50"
            >
              Upload + Ingest File
            </button>
          </div>
        </div>
        {ingestMessage ? <p className="mt-2 text-xs text-slate-300">{ingestMessage}</p> : null}
      </div>

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
                  {source.video_url ? (
                    <a
                      href={source.video_url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-lg border border-indigo-400/60 bg-indigo-500/20 px-3 py-1 text-xs text-indigo-100 hover:bg-indigo-500/30"
                    >
                      ▶ Open at Timestamp
                    </a>
                  ) : (
                    <button
                      type="button"
                      disabled
                      className="rounded-lg border border-slate-500/50 bg-slate-700/40 px-3 py-1 text-xs text-slate-300"
                    >
                      ▶ Timestamp Link Unavailable
                    </button>
                  )}
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
