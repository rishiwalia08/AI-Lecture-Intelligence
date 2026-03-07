import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

export function useHealth() {
  return useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 30_000 })
}

export function useKnowledgeGraph() {
  return useQuery({ queryKey: ['knowledge-graph'], queryFn: api.knowledgeGraph })
}

export function useFlashcards() {
  return useQuery({ queryKey: ['flashcards'], queryFn: api.flashcards })
}

export function useSummaries() {
  return useQuery({ queryKey: ['summaries'], queryFn: api.summaries })
}

export function useAsk() {
  return useMutation({
    mutationFn: (query) =>
      api.ask({
        query,
        top_k: 5,
      }),
  })
}
