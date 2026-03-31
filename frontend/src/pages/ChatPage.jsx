import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { fetchTranscript } from 'youtube-transcript'
import LoadingDots from '../components/LoadingDots'
import PageTitle from '../components/PageTitle'
import TypingText from '../components/TypingText'
import { useAsk, useIngestVideo, useIngestYoutube, useIngestYoutubeTranscript, useIngestText } from '../hooks/useApi'

function formatTimestamp(source) {
  if (source?.timestamp) return source.timestamp
  const seconds = Math.max(0, Number(source?.start_time || 0))
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function extractVideoId(url) {
  try {
    const urlObj = new URL(url)
    if (urlObj.hostname.includes('youtube.com')) {
      return urlObj.searchParams.get('v')
    }
    if (urlObj.hostname.includes('youtu.be')) {
      return urlObj.pathname.slice(1)
    }
  } catch {
    // Not a valid URL
  }
  return null
}

function ChatPage() {
  const [query, setQuery] = useState('')
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [lectureId, setLectureId] = useState('')
  const [selectedFile, setSelectedFile] = useState(null)
  const [manualText, setManualText] = useState('')
  const [showManualTextForm, setShowManualTextForm] = useState(false)
  const [ingestMessage, setIngestMessage] = useState('')
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hi! I am your AI Lecture Assistant. Ask me anything about your lectures.',
    },
  ])

  const askMutation = useAsk()
  const ingestYoutubeMutation = useIngestYoutube()
  const ingestYoutubeTranscriptMutation = useIngestYoutubeTranscript()
  const ingestVideoMutation = useIngestVideo()
  const ingestTextMutation = useIngestText()

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
    if (!url || ingestYoutubeMutation.isPending || ingestYoutubeTranscriptMutation.isPending) return

    setIngestMessage('Attempting to fetch transcript client-side...')

    try {
      const videoId = extractVideoId(url)
      if (!videoId) {
        setIngestMessage('❌ Invalid YouTube URL. Please check and try again.')
        return
      }

      // Try client-side transcript extraction first
      const transcript = await fetchTranscript(videoId)

      if (!transcript || transcript.length === 0) {
        // Fall back to server-side extraction
        setIngestMessage('Client-side extraction unavailable, trying server...')
        const result = await ingestYoutubeMutation.mutateAsync({ url, lectureId })
        setIngestMessage(`✅ Ingested ${result.lecture_id} (${result.num_chunks} chunks indexed)`)
        setYoutubeUrl('')
        return
      }

      // Got transcript client-side, send it to backend
      setIngestMessage('Processing transcript...')
      const result = await ingestYoutubeTranscriptMutation.mutateAsync({
        videoId,
        transcript: transcript.map((item) => ({
          text: item.text,
          start: item.offset / 1000,
          duration: (item.duration || 0) / 1000,
        })),
        title: null,
        lectureId,
      })

      setIngestMessage(`✅ Ingested ${result.lecture_id} (${result.num_chunks} chunks indexed)`)
      setYoutubeUrl('')
    } catch (error) {
      setIngestMessage(
        `❌ YouTube is blocked on our server. Please:\n1. Download the video/audio and upload directly, OR\n2. Paste the transcript text manually.\nError: ${error.message || 'Unknown error'}`
      )
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

  const onIngestText = async () => {
    const text = manualText.trim()
    if (!text || ingestTextMutation.isPending) return
    setIngestMessage('Processing text transcript...')
    try {
      const result = await ingestTextMutation.mutateAsync({
        text,
        title: lectureId || 'Manual Transcript',
        lectureId,
      })
      setIngestMessage(`✅ Ingested ${result.lecture_id} (${result.num_chunks} chunks indexed)`)
      setManualText('')
      setShowManualTextForm(false)
    } catch (error) {
      setIngestMessage(`❌ ${error.message || 'Failed to ingest text.'}`)
    }
  }

  return (
    <section className="flex h-full flex-col">
      <PageTitle title="AI Chat Assistant" subtitle="Ask lecture questions and get grounded answers with timestamps." />

      <div className="mb-4 rounded-2xl border border-slate-600/60 bg-slate-900/40 p-3">
        <p className="mb-2 text-xs uppercase tracking-wider text-slate-300">Ingest Lecture Content</p>

        {/* YouTube Section */}
        <div className="mb-3 rounded-xl border border-slate-700 bg-slate-800/50 p-2">
          <p className="mb-2 text-xs font-semibold text-slate-200">YouTube Video</p>
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
              disabled={ingestYoutubeMutation.isPending || ingestYoutubeTranscriptMutation.isPending}
              className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              {ingestYoutubeTranscriptMutation.isPending ? 'Processing...' : 'Ingest YouTube'}
            </button>
          </div>
        </div>

        {/* Video/Audio Upload Section */}
        <div className="mb-3 rounded-xl border border-slate-700 bg-slate-800/50 p-2">
          <p className="mb-2 text-xs font-semibold text-slate-200">Video/Audio File</p>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
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
        </div>

        {/* Manual Transcript Section */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-2">
          <button
            type="button"
            onClick={() => setShowManualTextForm(!showManualTextForm)}
            className="mb-2 text-xs font-semibold text-slate-300 hover:text-slate-100"
          >
            {showManualTextForm ? '▼' : '▶'} Paste Transcript Text (Manual)
          </button>
          {showManualTextForm && (
            <>
              <textarea
                value={manualText}
                onChange={(e) => setManualText(e.target.value)}
                placeholder="Paste lecture transcript or notes here..."
                className="mb-2 w-full rounded-lg border border-slate-600 bg-slate-900/70 px-3 py-2 text-sm text-slate-100 outline-none focus:ring-1 focus:ring-indigo-400"
                rows="4"
              />
              <button
                type="button"
                onClick={onIngestText}
                disabled={!manualText.trim() || ingestTextMutation.isPending}
                className="w-full rounded-lg bg-purple-600 px-3 py-2 text-sm font-semibold text-white hover:bg-purple-500 disabled:opacity-50"
              >
                {ingestTextMutation.isPending ? 'Processing...' : 'Ingest Text'}
              </button>
            </>
          )}
        </div>

        {ingestMessage ? <p className="mt-2 whitespace-pre-wrap text-xs text-slate-300">{ingestMessage}</p> : null}
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
          placeholder="Ask a question about your ingested lecture..."
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

