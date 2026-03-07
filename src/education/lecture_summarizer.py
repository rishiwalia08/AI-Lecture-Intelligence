"""
lecture_summarizer.py
=====================
Generate concise summaries from lecture transcripts using LLM.

Uses map-reduce approach for long transcripts:
1. Split into chunks
2. Summarize each chunk
3. Combine summaries into final summary
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.llm.llm_loader import load_llm
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LectureSummarizer:
    """
    Generate summaries from lecture transcripts using LLM.
    
    Attributes:
        llm: Language model instance
        model_config: LLM configuration
        chunk_size: Maximum tokens per chunk
        chunk_overlap: Overlap between chunks
    """
    
    # System prompt for initial chunk summarization
    CHUNK_SUMMARY_PROMPT = """You are an expert at creating concise, accurate summaries of educational content.
Your task is to summarize a portion of a lecture transcript.

Rules:
1. Capture key concepts and main ideas
2. Include important definitions
3. Preserve technical terminology
4. Be concise but comprehensive
5. Use clear, academic language
6. Focus on what students need to know

Create a summary that captures the essential information from this lecture segment."""
    
    # System prompt for final summary generation
    FINAL_SUMMARY_PROMPT = """You are an expert at synthesizing educational content.
You will receive multiple summaries of lecture segments. Your task is to create:
1. A coherent overall summary
2. A list of key concepts covered
3. Important definitions

Output format (JSON):
{
  "summary": "A comprehensive but concise summary of the entire lecture...",
  "key_concepts": ["concept1", "concept2", "concept3"],
  "definitions": {
    "term1": "definition1",
    "term2": "definition2"
  }
}

Rules:
- Summary should be 3-5 paragraphs
- Key concepts should be 5-10 items
- Definitions should be clear and concise
- Maintain academic tone
- Eliminate redundancy from chunk summaries"""
    
    def __init__(
        self,
        model_config: Optional[Dict[str, Any]] = None,
        chunk_size: int = 2000,
        chunk_overlap: int = 200,
    ):
        """
        Initialize the lecture summarizer.
        
        Args:
            model_config: LLM configuration dict
            chunk_size: Maximum characters per chunk
            chunk_overlap: Overlap between consecutive chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.model_config = model_config or {}
        
        # Load LLM
        logger.info("Loading LLM for lecture summarization...")
        try:
            self.llm = load_llm(self.model_config)
            logger.info("✅ LLM loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load LLM: {e}")
            raise
    
    def summarize_lecture(
        self,
        text: str,
        lecture_id: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate summary from lecture transcript using map-reduce approach.
        
        Args:
            text: Full lecture transcript
            lecture_id: Optional lecture identifier
            topic: Optional topic/subject
            
        Returns:
            Dictionary with summary, key_concepts, and definitions
        """
        if not text or not text.strip():
            logger.warning("Empty text provided, returning empty summary")
            return self._empty_summary()
        
        # Step 1: Split into chunks
        chunks = self._split_into_chunks(text)
        logger.info(f"Split lecture into {len(chunks)} chunks")
        
        # Step 2: Summarize each chunk (MAP phase)
        chunk_summaries = []
        for i, chunk in enumerate(chunks, 1):
            logger.info(f"Summarizing chunk {i}/{len(chunks)}")
            chunk_summary = self._summarize_chunk(chunk)
            if chunk_summary:
                chunk_summaries.append(chunk_summary)
        
        if not chunk_summaries:
            logger.warning("No chunk summaries generated")
            return self._empty_summary()
        
        # Step 3: Combine summaries (REDUCE phase)
        logger.info("Combining chunk summaries into final summary")
        final_summary = self._combine_summaries(chunk_summaries, topic)
        
        # Add metadata
        if lecture_id:
            final_summary["lecture_id"] = lecture_id
        if topic:
            final_summary["topic"] = topic
        
        logger.info(f"✅ Generated summary with {len(final_summary.get('key_concepts', []))} key concepts")
        
        return final_summary
    
    def summarize_from_transcript(
        self,
        transcript_path: Path,
    ) -> Dict[str, Any]:
        """
        Generate summary from a transcript JSON file.
        
        Args:
            transcript_path: Path to transcript JSON file
            
        Returns:
            Summary dictionary
        """
        logger.info(f"Generating summary from: {transcript_path.name}")
        
        try:
            with open(transcript_path, "r", encoding="utf-8") as f:
                transcript_data = json.load(f)
            
            # Extract text and metadata
            if "text" in transcript_data:
                text = transcript_data["text"]
            elif "segments" in transcript_data:
                text = " ".join(seg.get("text", "") for seg in transcript_data["segments"])
            else:
                logger.error(f"No text found in {transcript_path.name}")
                return self._empty_summary()
            
            lecture_id = transcript_data.get("lecture_id", transcript_path.stem)
            topic = transcript_data.get("topic", None)
            
            # Generate summary
            summary = self.summarize_lecture(text, lecture_id, topic)
            
            return summary
            
        except Exception as e:
            logger.error(f"Error processing transcript {transcript_path.name}: {e}")
            return self._empty_summary()
    
    def summarize_from_transcripts(
        self,
        transcript_dir: Path,
        limit: Optional[int] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Generate summaries from multiple transcript files.
        
        Args:
            transcript_dir: Directory containing transcript JSON files
            limit: Optional limit on number of files to process
            
        Returns:
            Dictionary mapping lecture_id to summary
        """
        transcript_files = sorted(transcript_dir.glob("*.json"))
        
        if limit:
            transcript_files = transcript_files[:limit]
        
        logger.info(f"Processing {len(transcript_files)} transcript files...")
        
        results = {}
        for transcript_path in transcript_files:
            lecture_id = transcript_path.stem.replace("_transcript", "")
            summary = self.summarize_from_transcript(transcript_path)
            
            if summary.get("summary"):
                results[lecture_id] = summary
                logger.info(f"✅ {lecture_id}: Summary generated")
            else:
                logger.warning(f"⚠️  {lecture_id}: Failed to generate summary")
        
        logger.info(f"\n✅ Generated {len(results)} summaries")
        
        return results
    
    def _split_into_chunks(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Full text to split
            
        Returns:
            List of text chunks
        """
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + self.chunk_size
            
            # Try to break at sentence boundary
            if end < text_length:
                # Look for sentence ending within last 200 chars
                chunk_end = text[start:end].rfind('. ')
                if chunk_end > self.chunk_size - 200:
                    end = start + chunk_end + 1
            
            chunks.append(text[start:end].strip())
            start = end - self.chunk_overlap
        
        return chunks
    
    def _summarize_chunk(self, chunk: str) -> str:
        """
        Summarize a single chunk of text.
        
        Args:
            chunk: Text chunk to summarize
            
        Returns:
            Summary text
        """
        try:
            messages = [
                {"role": "system", "content": self.CHUNK_SUMMARY_PROMPT},
                {"role": "user", "content": f"Summarize this lecture segment:\n\n{chunk}"},
            ]
            
            summary = self.llm.generate(messages)
            return summary.strip()
            
        except Exception as e:
            logger.error(f"Error summarizing chunk: {e}")
            return ""
    
    def _combine_summaries(
        self,
        chunk_summaries: List[str],
        topic: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Combine chunk summaries into final summary with key concepts and definitions.
        
        Args:
            chunk_summaries: List of chunk summaries
            topic: Optional topic for context
            
        Returns:
            Final summary dictionary
        """
        try:
            # Prepare combined text
            combined_text = "\n\n".join(f"Segment {i+1}:\n{summary}" 
                                       for i, summary in enumerate(chunk_summaries))
            
            user_prompt = "Create a comprehensive summary with key concepts and definitions from these lecture segment summaries:\n\n"
            if topic:
                user_prompt += f"Topic: {topic}\n\n"
            user_prompt += combined_text
            user_prompt += "\n\nReturn ONLY valid JSON with summary, key_concepts, and definitions fields."
            
            messages = [
                {"role": "system", "content": self.FINAL_SUMMARY_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
            
            response = self.llm.generate(messages)
            
            # Parse JSON response
            summary_data = self._parse_summary_response(response)
            
            return summary_data
            
        except Exception as e:
            logger.error(f"Error combining summaries: {e}")
            return self._empty_summary()
    
    def _parse_summary_response(self, response: str) -> Dict[str, Any]:
        """
        Parse LLM response to extract summary data.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Parsed summary dictionary
        """
        try:
            # Try to extract JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                
                # Validate structure
                summary_data = {
                    "summary": data.get("summary", "").strip(),
                    "key_concepts": data.get("key_concepts", []),
                    "definitions": data.get("definitions", {}),
                }
                
                return summary_data
            else:
                # Fallback: treat entire response as summary
                logger.warning("No JSON found, using fallback parsing")
                return {
                    "summary": response.strip(),
                    "key_concepts": [],
                    "definitions": {},
                }
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            # Fallback parsing
            return self._extract_summary_fallback(response)
    
    def _extract_summary_fallback(self, response: str) -> Dict[str, Any]:
        """
        Fallback method to extract summary components from unstructured text.
        
        Args:
            response: LLM response text
            
        Returns:
            Summary dictionary
        """
        summary_data = {
            "summary": "",
            "key_concepts": [],
            "definitions": {},
        }
        
        # Try to extract summary (usually first paragraph or section)
        lines = response.split('\n')
        summary_lines = []
        key_concepts = []
        
        in_summary = True
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for key concepts section
            if re.match(r'key\s+concepts?:', line, re.IGNORECASE):
                in_summary = False
                continue
            
            if in_summary:
                summary_lines.append(line)
            else:
                # Extract bullet points or numbered lists as key concepts
                concept = re.sub(r'^[-*•]\s*|\d+\.\s*', '', line)
                if concept:
                    key_concepts.append(concept)
        
        summary_data["summary"] = " ".join(summary_lines)
        summary_data["key_concepts"] = key_concepts[:10]  # Limit to 10
        
        return summary_data
    
    def _empty_summary(self) -> Dict[str, Any]:
        """Return empty summary structure."""
        return {
            "summary": "",
            "key_concepts": [],
            "definitions": {},
        }
    
    def save_summary(
        self,
        summary: Dict[str, Any],
        output_path: Path,
    ) -> None:
        """
        Save summary to JSON file.
        
        Args:
            summary: Summary dictionary
            output_path: Output file path
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Saved summary to {output_path}")
    
    @staticmethod
    def load_summary(summary_path: Path) -> Dict[str, Any]:
        """
        Load summary from JSON file.
        
        Args:
            summary_path: Path to summary JSON file
            
        Returns:
            Summary dictionary
        """
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = json.load(f)
            
            return summary
            
        except Exception as e:
            logger.error(f"Error loading summary from {summary_path}: {e}")
            return {
                "summary": "",
                "key_concepts": [],
                "definitions": {},
            }
