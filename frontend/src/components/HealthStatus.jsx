import { useEffect, useState } from 'react'
import { api } from '../services/api'

export default function HealthStatus() {
  const [status, setStatus] = useState('loading')
  const [documentsIndexed, setDocumentsIndexed] = useState(0)

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await api.health()
        setStatus(response.rag_ready ? 'ready' : 'offline')
        setDocumentsIndexed(response.documents_indexed || 0)
      } catch {
        setStatus('offline')
        setDocumentsIndexed(0)
      }
    }

    // Check immediately
    checkHealth()

    // Then check every 30 seconds
    const interval = setInterval(checkHealth, 30000)
    return () => clearInterval(interval)
  }, [])

  const getStatusDisplay = () => {
    if (status === 'loading') {
      return {
        icon: '⚪',
        text: 'Connecting...',
        color: 'text-gray-400',
      }
    }

    if (status === 'offline') {
      return {
        icon: '🔴',
        text: 'Server offline',
        color: 'text-red-400',
      }
    }

    if (status === 'ready' && documentsIndexed > 0) {
      return {
        icon: '🟢',
        text: `Ready — ${documentsIndexed} segments indexed`,
        color: 'text-green-400',
      }
    }

    if (status === 'ready' && documentsIndexed === 0) {
      return {
        icon: '🟡',
        text: 'No content yet — please ingest a lecture',
        color: 'text-yellow-400',
      }
    }

    return {
      icon: '⚪',
      text: 'Initializing...',
      color: 'text-gray-400',
    }
  }

  const display = getStatusDisplay()

  return (
    <div className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium ${display.color}`}>
      <span className="text-sm">{display.icon}</span>
      <span>{display.text}</span>
    </div>
  )
}
