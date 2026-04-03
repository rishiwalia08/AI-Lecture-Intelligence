import json
from services.llm import LLMService

class FlashcardBuilderService:
    def __init__(self, llm_service: LLMService) -> None:
        self.llm = llm_service

    def build_flashcards(self, chunks: list[dict]) -> list[dict]:
        text = " ".join([c["text"] for c in chunks])
        prompt = f"""
Analyze the following lecture transcript and create 5-10 spaced repetition flashcards covering the most important concepts.
Return strictly valid JSON in the exact structure below as an Array of objects, and nothing else. Do not use markdown tick wrappers.
[
  {{"front": "Question or Concept Name?", "back": "Detailed definition or answer based on the lecture."}}
]

Transcript:
{text[:10000]}
"""
        try:
            res = self.llm.chat("You are an expert AI tutor. You MUST output ONLY valid JSON without any markdown formatting. Do not say anything else.", prompt, temperature=0.0)
            
            cleaned = res.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
                
            return json.loads(cleaned.strip())
        except Exception:
            # Fallback to algorithmic chunk sampling when LLM string parsing breaks
            return self._build_fallback_flashcards(chunks)

    def _build_fallback_flashcards(self, chunks: list[dict]) -> list[dict]:
        cards = []
        if not chunks:
            return [{"front": "Empty Transcript", "back": "No audio chunks found."}]
            
        # Select up to 7 evenly spaced chunks
        step = max(1, len(chunks) // 7)
        for i in range(0, min(len(chunks), step * 7), step):
            text = chunks[i]["text"]
            words = text.split()
            if len(words) > 5:
                front_preview = " ".join(words[:5]) + "..."
                cards.append({
                    "front": f"What was discussed regarding: {front_preview}", 
                    "back": text
                })
        
        if not cards:
             cards = [{"front": "Concept Note", "back": chunks[0]["text"]}]
             
        return cards
