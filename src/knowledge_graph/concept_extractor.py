"""
concept_extractor.py
====================
Extract technical concepts and noun phrases from lecture transcripts using spaCy.

Uses en_core_web_trf model for high-accuracy NER and linguistic analysis.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

import spacy
from spacy.tokens import Doc, Span

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ConceptExtractor:
    """
    Extract technical concepts and noun phrases from text using spaCy.
    
    Attributes:
        nlp: spaCy language model (en_core_web_trf)
        min_concept_length: Minimum character length for valid concepts
        max_concept_length: Maximum character length for valid concepts
        stopwords: Set of words to exclude from concepts
    """
    
    def __init__(
        self,
        model_name: str = "en_core_web_trf",
        min_concept_length: int = 3,
        max_concept_length: int = 50,
    ):
        """
        Initialize the concept extractor.
        
        Args:
            model_name: spaCy model to use (default: en_core_web_trf)
            min_concept_length: Minimum character length for concepts
            max_concept_length: Maximum character length for concepts
        """
        self.min_concept_length = min_concept_length
        self.max_concept_length = max_concept_length
        
        logger.info(f"Loading spaCy model: {model_name}")
        try:
            self.nlp = spacy.load(model_name)
            logger.info(f"✅ Model {model_name} loaded successfully")
        except OSError:
            logger.error(
                f"❌ Model {model_name} not found. Install with: "
                f"python -m spacy download {model_name}"
            )
            raise
        
        # Define stopwords to filter out common words
        self.stopwords = self._get_stopwords()
    
    def _get_stopwords(self) -> Set[str]:
        """Get set of stopwords to exclude from concepts."""
        common_stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "up", "about", "into", "through", "during",
            "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
            "do", "does", "did", "will", "would", "should", "could", "may", "might",
            "must", "can", "this", "that", "these", "those", "i", "you", "he", "she",
            "it", "we", "they", "what", "which", "who", "when", "where", "why", "how",
            "all", "each", "every", "both", "few", "more", "most", "other", "some",
            "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
            "very", "just", "now", "also", "back", "even", "still", "way", "well"
        }
        return common_stopwords
    
    def extract_concepts(self, text: str) -> List[str]:
        """
        Extract technical concepts and noun phrases from text.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of unique concepts found in text
            
        Example:
            >>> extractor = ConceptExtractor()
            >>> text = "Backpropagation is used to train neural networks."
            >>> concepts = extractor.extract_concepts(text)
            >>> print(concepts)
            ['backpropagation', 'neural networks']
        """
        if not text or not text.strip():
            return []
        
        doc = self.nlp(text)
        concepts = set()
        
        # Extract noun chunks
        for chunk in doc.noun_chunks:
            concept = self._clean_concept(chunk.text)
            if self._is_valid_concept(concept):
                concepts.add(concept.lower())
        
        # Extract named entities (technical terms, products, etc.)
        for ent in doc.ents:
            if ent.label_ in ["PRODUCT", "ORG", "NORP", "FAC", "LAW", "LANGUAGE"]:
                concept = self._clean_concept(ent.text)
                if self._is_valid_concept(concept):
                    concepts.add(concept.lower())
        
        # Extract compound nouns (consecutive nouns)
        for i, token in enumerate(doc):
            if token.pos_ == "NOUN":
                compound = self._extract_compound_noun(doc, i)
                if compound and self._is_valid_concept(compound):
                    concepts.add(compound.lower())
        
        return sorted(list(concepts))
    
    def _extract_compound_noun(self, doc: Doc, start_idx: int) -> str:
        """
        Extract compound noun phrase starting at given index.
        
        Args:
            doc: spaCy Doc object
            start_idx: Starting token index
            
        Returns:
            Compound noun phrase or empty string
        """
        tokens = [doc[start_idx].text]
        
        # Look ahead for more nouns
        for i in range(start_idx + 1, len(doc)):
            if doc[i].pos_ in ["NOUN", "PROPN"]:
                tokens.append(doc[i].text)
            else:
                break
        
        if len(tokens) > 1:
            return " ".join(tokens)
        return ""
    
    def _clean_concept(self, text: str) -> str:
        """
        Clean and normalize concept text.
        
        Args:
            text: Raw concept text
            
        Returns:
            Cleaned concept text
        """
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text).strip()
        
        # Remove leading/trailing articles and prepositions
        text = re.sub(r"^(the|a|an|in|on|at|to|for|of|with)\s+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+(the|a|an|in|on|at|to|for|of|with)$", "", text, flags=re.IGNORECASE)
        
        return text
    
    def _is_valid_concept(self, concept: str) -> bool:
        """
        Check if a concept is valid based on length and content.
        
        Args:
            concept: Concept text to validate
            
        Returns:
            True if concept is valid, False otherwise
        """
        if not concept:
            return False
        
        # Check length
        if len(concept) < self.min_concept_length or len(concept) > self.max_concept_length:
            return False
        
        # Check if it's just a stopword
        if concept.lower() in self.stopwords:
            return False
        
        # Check if it contains at least one letter
        if not re.search(r"[a-zA-Z]", concept):
            return False
        
        # Check if it's mostly numbers or symbols
        alpha_ratio = sum(c.isalpha() or c.isspace() for c in concept) / len(concept)
        if alpha_ratio < 0.5:
            return False
        
        return True
    
    def extract_concepts_with_context(
        self, text: str
    ) -> List[Dict[str, str]]:
        """
        Extract concepts with their surrounding context sentences.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of dictionaries with 'concept' and 'context' keys
        """
        doc = self.nlp(text)
        results = []
        
        for sent in doc.sents:
            concepts = self.extract_concepts(sent.text)
            for concept in concepts:
                results.append({
                    "concept": concept,
                    "context": sent.text.strip()
                })
        
        return results
    
    def extract_concept_pairs(
        self, text: str, max_distance: int = 10
    ) -> List[Tuple[str, str]]:
        """
        Extract pairs of concepts that appear close together in text.
        
        This is useful for detecting potential relationships between concepts.
        
        Args:
            text: Input text to analyze
            max_distance: Maximum token distance between concept pairs
            
        Returns:
            List of concept pairs (tuples)
        """
        doc = self.nlp(text)
        concept_positions: List[Tuple[str, int]] = []
        
        # Extract concepts with their positions
        for chunk in doc.noun_chunks:
            concept = self._clean_concept(chunk.text)
            if self._is_valid_concept(concept):
                concept_positions.append((concept.lower(), chunk.start))
        
        # Find pairs within max_distance
        pairs = []
        for i, (concept1, pos1) in enumerate(concept_positions):
            for concept2, pos2 in concept_positions[i + 1:]:
                if abs(pos2 - pos1) <= max_distance:
                    pairs.append((concept1, concept2))
        
        return pairs
    
    def batch_extract_concepts(
        self, texts: List[str], show_progress: bool = True
    ) -> Dict[int, List[str]]:
        """
        Extract concepts from multiple texts efficiently.
        
        Args:
            texts: List of texts to process
            show_progress: Whether to show progress bar
            
        Returns:
            Dictionary mapping text index to list of concepts
        """
        results = {}
        
        if show_progress:
            from tqdm import tqdm
            texts_iter = tqdm(texts, desc="Extracting concepts")
        else:
            texts_iter = texts
        
        for idx, text in enumerate(texts_iter):
            try:
                concepts = self.extract_concepts(text)
                results[idx] = concepts
            except Exception as e:
                logger.error(f"Error processing text {idx}: {e}")
                results[idx] = []
        
        return results
