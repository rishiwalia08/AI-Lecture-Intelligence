"""
test_concept_extractor.py
==========================
Unit tests for the ConceptExtractor class.
"""

import pytest

from src.knowledge_graph.concept_extractor import ConceptExtractor


@pytest.fixture
def extractor():
    """Create a ConceptExtractor instance."""
    return ConceptExtractor(model_name="en_core_web_sm")  # Use smaller model for tests


class TestConceptExtractor:
    """Test suite for ConceptExtractor."""
    
    def test_initialization(self, extractor):
        """Test that extractor initializes correctly."""
        assert extractor.nlp is not None
        assert extractor.min_concept_length == 3
        assert extractor.max_concept_length == 50
        assert len(extractor.stopwords) > 0
    
    def test_extract_concepts_basic(self, extractor):
        """Test basic concept extraction."""
        text = "Backpropagation is used to train neural networks."
        concepts = extractor.extract_concepts(text)
        
        assert isinstance(concepts, list)
        assert len(concepts) > 0
        assert "neural networks" in concepts or "backpropagation" in concepts
    
    def test_extract_concepts_empty_text(self, extractor):
        """Test extraction from empty text."""
        assert extractor.extract_concepts("") == []
        assert extractor.extract_concepts("   ") == []
    
    def test_extract_concepts_technical_terms(self, extractor):
        """Test extraction of technical terms."""
        text = "Machine learning algorithms use gradient descent for optimization."
        concepts = extractor.extract_concepts(text)
        
        assert len(concepts) > 0
        # Should extract some technical terms
        technical_terms = ["machine learning", "algorithms", "gradient descent", "optimization"]
        found = [term for term in technical_terms if term in concepts]
        assert len(found) > 0
    
    def test_clean_concept(self, extractor):
        """Test concept cleaning."""
        assert extractor._clean_concept("  the neural network  ") == "neural network"
        assert extractor._clean_concept("a machine learning") == "machine learning"
        assert extractor._clean_concept("deep learning of data") == "deep learning"
    
    def test_is_valid_concept(self, extractor):
        """Test concept validation."""
        assert extractor._is_valid_concept("neural network") is True
        assert extractor._is_valid_concept("ai") is False  # Too short
        assert extractor._is_valid_concept("the") is False  # Stopword
        assert extractor._is_valid_concept("123") is False  # No letters
        assert extractor._is_valid_concept("a" * 100) is False  # Too long
    
    def test_extract_concept_pairs(self, extractor):
        """Test concept pair extraction."""
        text = "Backpropagation is used to train neural networks efficiently."
        pairs = extractor.extract_concept_pairs(text, max_distance=10)
        
        assert isinstance(pairs, list)
        # Should find some pairs if concepts are close
        if len(pairs) > 0:
            assert all(isinstance(p, tuple) and len(p) == 2 for p in pairs)
    
    def test_extract_concepts_with_context(self, extractor):
        """Test extraction with context."""
        text = "Machine learning is powerful. Neural networks are popular."
        results = extractor.extract_concepts_with_context(text)
        
        assert isinstance(results, list)
        assert len(results) > 0
        assert all("concept" in r and "context" in r for r in results)
    
    def test_batch_extract_concepts(self, extractor):
        """Test batch extraction."""
        texts = [
            "Machine learning is a subset of AI.",
            "Neural networks are used for deep learning.",
            "Backpropagation trains neural networks.",
        ]
        
        results = extractor.batch_extract_concepts(texts, show_progress=False)
        
        assert isinstance(results, dict)
        assert len(results) == len(texts)
        assert all(isinstance(concepts, list) for concepts in results.values())
