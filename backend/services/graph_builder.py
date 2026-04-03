import json
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from services.llm import LLMService

class GraphBuilderService:
    def __init__(self, llm_service: LLMService) -> None:
        self.llm = llm_service

    def build_graph(self, chunks: list[dict]) -> dict:
        text = " ".join([c["text"] for c in chunks])
        prompt = f"""
Analyze the following lecture transcript and extract a knowledge graph.
Identify the main concepts (nodes) and the relationships between them (links).
Limit to the 15 most important concepts.
Return strictly valid JSON in the exact structure below, and nothing else. Do not use markdown wrappers.
{{
  "nodes": [
    {{"id": "ConceptName", "name": "Concept Name", "val": 2}}
  ],
  "links": [
    {{"source": "ConceptName1", "target": "ConceptName2"}}
  ]
}}

Transcript:
{text[:10000]}
"""
        try:
            # We enforce temperature 0 to try and force rigid JSON parsing
            res = self.llm.chat("You are an expert data extraction AI. You MUST output ONLY valid JSON without any markdown formatting or ticks. Do not say anything else.", prompt, temperature=0.0)
            
            # Safe clean of markdown just in case the LLM ignores instructions
            cleaned = res.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
                
            return json.loads(cleaned.strip())
        except Exception as e:
            # Fallback to TF-IDF algorithmic NLP when the LLM is too small to output valid JSON
            return self._build_fallback_graph(chunks)

    def _build_fallback_graph(self, chunks: list[dict]) -> dict:
        texts = [c["text"] for c in chunks if len(c["text"]) > 10]
        if not texts:
            return {"nodes": [{"id": "Empty", "name": "No Transcript Data", "val": 1}], "links": []}
            
        try:
            vectorizer = TfidfVectorizer(stop_words='english', max_features=15)
            tfidf_matrix = vectorizer.fit_transform(texts)
            feature_names = vectorizer.get_feature_names_out()
        except Exception:
            return {"nodes": [{"id": "Error", "name": "TF-IDF extraction failed", "val": 1}], "links": []}

        nodes = [{"id": str(word), "name": str(word).title(), "val": int(np.random.randint(2, 6))} for word in feature_names]
        links = []
        
        for doc_idx in range(len(texts)):
            row = tfidf_matrix[doc_idx].toarray()[0]
            indices = np.where(row > 0.0)[0]
            for i in range(len(indices)):
                for j in range(i+1, len(indices)):
                    links.append({
                        "source": str(feature_names[indices[i]]),
                        "target": str(feature_names[indices[j]])
                    })
                    
        # Filter duplicates
        unique_links = []
        seen = set()
        for link in links:
            pair = tuple(sorted([link["source"], link["target"]]))
            if pair not in seen:
                seen.add(pair)
                unique_links.append(link)

        return {"nodes": nodes, "links": unique_links[:25]}
