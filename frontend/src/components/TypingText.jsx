import { useEffect, useMemo, useState } from 'react'

function TypingText({ text = '', speed = 12 }) {
  const [index, setIndex] = useState(0)
  const safeText = useMemo(() => text || '', [text])

  useEffect(() => {
    setIndex(0)
  }, [safeText])

  useEffect(() => {
    if (index >= safeText.length) {
      return
    }
    const timer = setTimeout(() => setIndex((v) => v + 1), speed)
    return () => clearTimeout(timer)
  }, [index, safeText, speed])

  return <span>{safeText.slice(0, index)}</span>
}

export default TypingText
