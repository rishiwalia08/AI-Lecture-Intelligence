import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import LoadingDots from '../components/LoadingDots'
import PageTitle from '../components/PageTitle'
import { useSummaries } from '../hooks/useApi'

function SummariesPage() {
  const { data, isLoading } = useSummaries()
  const lectures = data?.lectures || []
  const [openId, setOpenId] = useState(null)

  return (
    <section>
      <PageTitle title="Lecture Summaries" subtitle="Browse concise summaries and key topics for each lecture." />
      {isLoading ? <LoadingDots label="Loading summaries..." /> : null}

      <div className="space-y-3">
        {lectures.map((lecture) => {
          const expanded = openId === lecture.lecture_id
          return (
            <motion.div
              key={lecture.lecture_id}
              layout
              className="glass rounded-2xl border border-slate-700/60 p-4"
            >
              <button
                type="button"
                onClick={() => setOpenId((v) => (v === lecture.lecture_id ? null : lecture.lecture_id))}
                className="flex w-full items-center justify-between text-left"
              >
                <div>
                  <p className="text-sm font-semibold text-white">{lecture.lecture_id}</p>
                  <p className="mt-1 text-xs text-slate-300">{(lecture.key_topics || []).slice(0, 3).join(' • ')}</p>
                </div>
                <span className="text-slate-300">{expanded ? '−' : '+'}</span>
              </button>

              <AnimatePresence>
                {expanded ? (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="mt-3 rounded-xl border border-slate-600/50 bg-slate-900/40 p-3">
                      <p className="mb-2 text-xs uppercase tracking-wider text-indigo-200">Key Topics</p>
                      <div className="mb-3 flex flex-wrap gap-2">
                        {(lecture.key_topics || []).map((topic) => (
                          <span key={topic} className="rounded-full border border-indigo-400/40 bg-indigo-500/15 px-2 py-1 text-xs text-indigo-100">
                            {topic}
                          </span>
                        ))}
                      </div>
                      <p className="text-sm leading-relaxed text-slate-100">{lecture.summary}</p>
                    </div>
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </motion.div>
          )
        })}
      </div>
    </section>
  )
}

export default SummariesPage
