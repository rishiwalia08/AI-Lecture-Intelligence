const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed: ${response.status}`)
  }

  return response.json()
}

async function requestForm(path, formData) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed: ${response.status}`)
  }

  return response.json()
}

export const api = {
  baseUrl: API_BASE_URL,
  ask: (payload) => request('/ask', { method: 'POST', body: JSON.stringify(payload) }),
  health: () => request('/health'),
  knowledgeGraph: () => request('/knowledge_graph'),
  ingestYoutube: (payload) => request('/ingest_youtube', { method: 'POST', body: JSON.stringify(payload) }),
  ingestVideo: (file, lectureId = '') => {
    const form = new FormData()
    form.append('media', file)
    if (lectureId.trim()) form.append('lecture_id', lectureId.trim())
    return requestForm('/ingest_video', form)
  },
  flashcards: () => request('/flashcards'),
  summaries: () => request('/summaries'),
}
