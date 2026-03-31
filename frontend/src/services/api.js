const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

async function extractErrorMessage(response) {
  const text = await response.text()
  if (!text) return `Request failed: ${response.status}`
  try {
    const parsed = JSON.parse(text)
    if (typeof parsed?.detail === 'string' && parsed.detail.trim()) return parsed.detail
    if (typeof parsed?.message === 'string' && parsed.message.trim()) return parsed.message
  } catch {
    // keep raw text
  }
  return text
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response))
  }

  return response.json()
}

async function requestForm(path, formData) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response))
  }

  return response.json()
}

export const api = {
  baseUrl: API_BASE_URL,
  ask: (payload) => request('/ask', { method: 'POST', body: JSON.stringify(payload) }),
  health: () => request('/health'),
  knowledgeGraph: () => request('/knowledge_graph'),
  ingestYoutube: (payload) => request('/ingest_youtube', { method: 'POST', body: JSON.stringify(payload) }),
  ingestYoutubeTranscript: (payload) => request('/ingest_youtube_transcript', { method: 'POST', body: JSON.stringify(payload) }),
  ingestVideo: (file, lectureId = '') => {
    const form = new FormData()
    form.append('media', file)
    if (lectureId.trim()) form.append('lecture_id', lectureId.trim())
    return requestForm('/ingest_video', form)
  },
  ingestText: (payload) => request('/ingest_text', { method: 'POST', body: JSON.stringify(payload) }),
  flashcards: () => request('/flashcards'),
  summaries: () => request('/summaries'),
}
