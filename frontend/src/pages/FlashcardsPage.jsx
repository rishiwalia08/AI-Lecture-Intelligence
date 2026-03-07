import { useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import PageTitle from '../components/PageTitle'
import LoadingDots from '../components/LoadingDots'
import { useFlashcards } from '../hooks/useApi'

function FlashcardsPage() {
  const { data, isLoading } = useFlashcards()
  const cards = useMemo(() => data?.flashcards || [], [data])
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)

  const active = cards[index]

  const goNext = () => {
    if (!cards.length) return
    setFlipped(false)
    setIndex((i) => (i + 1) % cards.length)
  }

  const goPrev = () => {
    if (!cards.length) return
    setFlipped(false)
    setIndex((i) => (i - 1 + cards.length) % cards.length)
  }

  const shuffle = () => {
    if (!cards.length) return
    setFlipped(false)
    setIndex(Math.floor(Math.random() * cards.length))
  }

  return (
    <section>
      <PageTitle title="Flashcard Study Mode" subtitle="Flip cards to test recall and improve retention." />
      {isLoading ? <LoadingDots label="Preparing flashcards..." /> : null}

      {active ? (
        <div className="mx-auto max-w-2xl">
          <div className="mb-3 text-center text-xs text-slate-300">
            Card {index + 1} / {cards.length}
          </div>

          <AnimatePresence mode="wait">
            <motion.button
              key={`${index}-${flipped ? 'back' : 'front'}`}
              onClick={() => setFlipped((v) => !v)}
              className="glass min-h-64 w-full rounded-3xl border border-indigo-400/35 p-8 text-left"
              initial={{ opacity: 0, rotateY: -90 }}
              animate={{ opacity: 1, rotateY: 0 }}
              exit={{ opacity: 0, rotateY: 90 }}
              transition={{ duration: 0.35 }}
              type="button"
            >
              <p className="mb-3 text-xs uppercase tracking-wider text-indigo-200">{flipped ? 'Answer' : 'Question'}</p>
              <p className="text-lg leading-relaxed text-slate-100">{flipped ? active.answer : active.question}</p>
              <p className="mt-6 text-xs text-slate-400">Click card to flip</p>
            </motion.button>
          </AnimatePresence>

          <div className="mt-4 flex items-center justify-center gap-2">
            <button onClick={goPrev} type="button" className="rounded-xl border border-slate-500 bg-slate-800/60 px-4 py-2 text-sm">Previous</button>
            <button onClick={shuffle} type="button" className="rounded-xl border border-indigo-400/60 bg-indigo-500/20 px-4 py-2 text-sm text-indigo-100">Shuffle</button>
            <button onClick={goNext} type="button" className="rounded-xl border border-slate-500 bg-slate-800/60 px-4 py-2 text-sm">Next</button>
          </div>
        </div>
      ) : !isLoading ? (
        <div className="rounded-xl border border-slate-700 bg-slate-900/35 p-4 text-sm text-slate-300">No flashcards available yet.</div>
      ) : null}
    </section>
  )
}

export default FlashcardsPage
