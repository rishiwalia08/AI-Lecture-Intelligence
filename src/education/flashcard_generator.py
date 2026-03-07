"""
flashcard_generator.py
======================
Generate study flashcards from lecture transcripts using LLM.

Creates question-answer pairs for active learning and recall practice.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.llm.llm_loader import load_llm
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FlashcardGenerator:
    """
    Generate study flashcards from lecture content using LLM.
    
    Attributes:
        llm: Language model instance
        model_config: LLM configuration
        max_cards_per_chunk: Maximum flashcards per text chunk
    """
    
    # System prompt for flashcard generation
    SYSTEM_PROMPT = """You are an expert educational content creator specializing in active learning.
Your task is to create high-quality study flashcards from lecture content.

Rules:
1. Generate clear, concise questions that test understanding
2. Focus on key concepts, definitions, and important facts
3. Provide accurate, complete answers
4. Use simple language
5. Each flashcard should test ONE concept
6. Avoid trivial or overly complex questions
7. Return ONLY valid JSON array format

Output format:
[
  {
    "question": "What is gradient descent?",
    "answer": "An optimization algorithm that iteratively adjusts parameters to minimize a loss function by moving in the direction of steepest descent."
  },
  {
    "question": "What is the purpose of backpropagation?",
    "answer": "To compute gradients of the loss function with respect to network weights, enabling efficient training of neural networks."
  }
]"""
    
    def __init__(
        self,
        model_config: Optional[Dict[str, Any]] = None,
        max_cards_per_chunk: int = 10,
    ):
        """
        Initialize the flashcard generator.
        
        Args:
            model_config: LLM configuration dict (provider, model, temperature, etc.)
            max_cards_per_chunk: Maximum flashcards to generate per text chunk
        """
        self.max_cards_per_chunk = max_cards_per_chunk
        self.model_config = model_config or {}
        
        # Load LLM
        logger.info("Loading LLM for flashcard generation...")
        try:
            self.llm = load_llm(self.model_config)
            logger.info("✅ LLM loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load LLM: {e}")
            raise
    
    def generate_flashcards(
        self, 
        text: str, 
        lecture_id: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        Generate flashcards from text using LLM.
        
        Args:
            text: Lecture content to create flashcards from
            lecture_id: Optional lecture identifier
            topic: Optional topic/subject for context
            
        Returns:
            List of flashcard dictionaries with 'question' and 'answer' keys
        """
        if not text or not text.strip():
            logger.warning("Empty text provided, no flashcards generated")
            return []
        
        # Build user prompt
        user_prompt = self._build_user_prompt(text, lecture_id, topic)
        
        # Generate with LLM
        try:
            response = self._call_llm(user_prompt)
            flashcards = self._parse_response(response)
            
            # Add metadata
            for card in flashcards:
                if lecture_id:
                    card["lecture_id"] = lecture_id
                if topic:
                    card["topic"] = topic
            
            logger.info(f"Generated {len(flashcards)} flashcards")
            return flashcards
            
        except Exception as e:
            logger.error(f"Error generating flashcards: {e}")
            return []
    
    def generate_from_transcript(
        self,
        transcript_path: Path,
    ) -> List[Dict[str, str]]:
        """
        Generate flashcards from a transcript JSON file.
        
        Args:
            transcript_path: Path to transcript JSON file
            
        Returns:
            List of flashcards
        """
        logger.info(f"Generating flashcards from: {transcript_path.name}")
        
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
                return []
            
            lecture_id = transcript_data.get("lecture_id", transcript_path.stem)
            topic = transcript_data.get("topic", None)
            
            # Generate flashcards
            flashcards = self.generate_flashcards(text, lecture_id, topic)
            
            return flashcards
            
        except Exception as e:
            logger.error(f"Error processing transcript {transcript_path.name}: {e}")
            return []
    
    def generate_from_transcripts(
        self,
        transcript_dir: Path,
        limit: Optional[int] = None,
    ) -> Dict[str, List[Dict[str, str]]]:
        """
        Generate flashcards from multiple transcript files.
        
        Args:
            transcript_dir: Directory containing transcript JSON files
            limit: Optional limit on number of files to process
            
        Returns:
            Dictionary mapping lecture_id to list of flashcards
        """
        transcript_files = sorted(transcript_dir.glob("*.json"))
        
        if limit:
            transcript_files = transcript_files[:limit]
        
        logger.info(f"Processing {len(transcript_files)} transcript files...")
        
        results = {}
        for transcript_path in transcript_files:
            lecture_id = transcript_path.stem.replace("_transcript", "")
            flashcards = self.generate_from_transcript(transcript_path)
            
            if flashcards:
                results[lecture_id] = flashcards
                logger.info(f"✅ {lecture_id}: {len(flashcards)} flashcards")
            else:
                logger.warning(f"⚠️  {lecture_id}: No flashcards generated")
        
        total_cards = sum(len(cards) for cards in results.values())
        logger.info(f"\n✅ Generated {total_cards} total flashcards from {len(results)} lectures")
        
        return results
    
    def _build_user_prompt(
        self, 
        text: str, 
        lecture_id: Optional[str], 
        topic: Optional[str]
    ) -> str:
        """Build the user prompt for LLM."""
        prompt = f"Generate {self.max_cards_per_chunk} study flashcards from this lecture content.\n\n"
        
        if topic:
            prompt += f"Topic: {topic}\n\n"
        
        if lecture_id:
            prompt += f"Lecture ID: {lecture_id}\n\n"
        
        prompt += f"Content:\n{text[:3000]}\n\n"  # Limit text length
        prompt += "Return ONLY a JSON array of flashcards with 'question' and 'answer' fields."
        
        return prompt
    
    def _call_llm(self, user_prompt: str) -> str:
        """
        Call the LLM with system and user prompts.
        
        Args:
            user_prompt: User message
            
        Returns:
            LLM response text
        """
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        
        response = self.llm.generate(messages)
        return response
    
    def _parse_response(self, response: str) -> List[Dict[str, str]]:
        """
        Parse LLM response to extract flashcards.
        
        Args:
            response: Raw LLM response text
            
        Returns:
            List of flashcard dictionaries
        """
        # Try to extract JSON from response
        try:
            # Look for JSON array in response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                flashcards = json.loads(json_str)
                
                # Validate structure
                valid_flashcards = []
                for card in flashcards:
                    if isinstance(card, dict) and "question" in card and "answer" in card:
                        valid_flashcards.append({
                            "question": str(card["question"]).strip(),
                            "answer": str(card["answer"]).strip(),
                        })
                
                return valid_flashcards
            else:
                logger.warning("No JSON array found in LLM response")
                return []
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            # Try to extract Q&A pairs manually
            return self._extract_qa_pairs_fallback(response)
    
    def _extract_qa_pairs_fallback(self, response: str) -> List[Dict[str, str]]:
        """
        Fallback method to extract Q&A pairs from unstructured text.
        
        Args:
            response: LLM response text
            
        Returns:
            List of flashcards
        """
        flashcards = []
        
        # Try to find Q: ... A: ... patterns
        qa_pattern = r'(?:Q(?:uestion)?|q):\s*(.+?)\s*(?:A(?:nswer)?|a):\s*(.+?)(?=(?:Q(?:uestion)?|q):|$)'
        matches = re.findall(qa_pattern, response, re.DOTALL | re.IGNORECASE)
        
        for question, answer in matches:
            flashcards.append({
                "question": question.strip(),
                "answer": answer.strip(),
            })
        
        if flashcards:
            logger.info(f"Extracted {len(flashcards)} flashcards using fallback method")
        
        return flashcards
    
    def save_flashcards(
        self,
        flashcards: List[Dict[str, str]],
        output_path: Path,
        format: str = "json",
    ) -> None:
        """
        Save flashcards to file.
        
        Args:
            flashcards: List of flashcard dictionaries
            output_path: Output file path
            format: Output format ('json', 'csv', 'anki')
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "json":
            self._save_json(flashcards, output_path)
        elif format == "csv":
            self._save_csv(flashcards, output_path)
        elif format == "anki":
            self._save_anki(flashcards, output_path)
        else:
            logger.error(f"Unknown format: {format}")
            raise ValueError(f"Unsupported format: {format}")
    
    def _save_json(self, flashcards: List[Dict[str, str]], output_path: Path) -> None:
        """Save flashcards as JSON."""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(flashcards, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Saved {len(flashcards)} flashcards to {output_path}")
    
    def _save_csv(self, flashcards: List[Dict[str, str]], output_path: Path) -> None:
        """Save flashcards as CSV."""
        import csv
        
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            if not flashcards:
                return
            
            fieldnames = list(flashcards[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flashcards)
        
        logger.info(f"💾 Saved {len(flashcards)} flashcards to {output_path}")
    
    def _save_anki(self, flashcards: List[Dict[str, str]], output_path: Path) -> None:
        """
        Save flashcards in Anki import format (tab-separated).
        
        Format: question<TAB>answer
        """
        with open(output_path, "w", encoding="utf-8") as f:
            for card in flashcards:
                # Anki format: front\tback
                question = card["question"].replace("\t", " ").replace("\n", "<br>")
                answer = card["answer"].replace("\t", " ").replace("\n", "<br>")
                f.write(f"{question}\t{answer}\n")
        
        logger.info(f"💾 Saved {len(flashcards)} flashcards to {output_path} (Anki format)")
    
    @staticmethod
    def load_flashcards(flashcard_path: Path) -> List[Dict[str, str]]:
        """
        Load flashcards from JSON file.
        
        Args:
            flashcard_path: Path to flashcards JSON file
            
        Returns:
            List of flashcard dictionaries
        """
        try:
            with open(flashcard_path, "r", encoding="utf-8") as f:
                flashcards = json.load(f)
            
            if not isinstance(flashcards, list):
                logger.error(f"Invalid flashcard format in {flashcard_path}")
                return []
            
            return flashcards
            
        except Exception as e:
            logger.error(f"Error loading flashcards from {flashcard_path}: {e}")
            return []
