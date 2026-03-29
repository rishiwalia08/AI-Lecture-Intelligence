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

export const api = {
  baseUrl: API_BASE_URL,
  ask: (payload) => request('/ask', { method: 'POST', body: JSON.stringify(payload) }),
  health: () => request('/health'),
  knowledgeGraph: () => request('/knowledge_graph'),
  flashcards: async () => {
    try {
      return await request('/flashcards')
    } catch {
      return {
        lecture_id: 'demo_lecture',
        flashcards: [
          { question: 'What is gradient descent?', answer: 'An optimization algorithm minimizing loss iteratively.' },
          { question: 'Why use backpropagation?', answer: 'To compute gradients efficiently across network layers.' },
          { question: 'What does a CNN capture first?', answer: 'Low-level local patterns such as edges and textures.' },
        ],
      }
    }
  },
  summaries: async () => {
    try {
      return await request('/summaries')
    } catch {
      return {
        lectures: [
          {
            lecture_id: 'lecture_01',
            key_topics: ['Introduction', 'Optimization', 'Model Training'],
            summary: 'This lecture introduces machine learning workflows, optimization basics, and practical model training steps.',
          },
          {
            lecture_id: 'lecture_02',
            key_topics: ['Backpropagation', 'Neural Nets', 'Regularization'],
            summary: 'This lecture explains backpropagation mechanics, gradient flow, and methods to improve generalization.',
          },
        ],
      }
    }
  },
}
