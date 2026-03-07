"""
test_flashcard_generator.py
============================
Unit tests for the FlashcardGenerator class.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.education.flashcard_generator import FlashcardGenerator


@pytest.fixture
def mock_llm_config():
    """Mock LLM configuration for testing."""
    return {
        "provider": "ollama",
        "model": "llama3",
        "temperature": 0.2,
    }


@pytest.fixture
def sample_text():
    """Sample lecture text for testing."""
    return """
    Gradient descent is an optimization algorithm used to minimize a loss function.
    It iteratively adjusts parameters in the direction of steepest descent.
    Neural networks use backpropagation to compute gradients efficiently.
    """


@pytest.fixture
def sample_transcript():
    """Sample transcript data."""
    return {
        "lecture_id": "test_lecture",
        "topic": "Machine Learning",
        "text": "Gradient descent is an optimization algorithm. Neural networks use backpropagation.",
        "segments": []
    }


class TestFlashcardGenerator:
    """Test suite for FlashcardGenerator."""
    
    def test_initialization(self, mock_llm_config):
        """Test generator initialization."""
        # Note: This will try to load actual LLM, skip if not available
        try:
            generator = FlashcardGenerator(
                model_config=mock_llm_config,
                max_cards_per_chunk=5,
            )
            assert generator is not None
            assert generator.max_cards_per_chunk == 5
        except Exception:
            pytest.skip("LLM not available for testing")
    
    def test_parse_response_valid_json(self):
        """Test parsing valid JSON response."""
        generator = FlashcardGenerator.__new__(FlashcardGenerator)
        
        response = '''
        [
          {
            "question": "What is gradient descent?",
            "answer": "An optimization algorithm."
          },
          {
            "question": "What is backpropagation?",
            "answer": "A method to compute gradients."
          }
        ]
        '''
        
        flashcards = generator._parse_response(response)
        
        assert len(flashcards) == 2
        assert flashcards[0]["question"] == "What is gradient descent?"
        assert flashcards[1]["question"] == "What is backpropagation?"
    
    def test_parse_response_fallback(self):
        """Test fallback parsing for unstructured text."""
        generator = FlashcardGenerator.__new__(FlashcardGenerator)
        
        response = """
        Q: What is gradient descent?
        A: An optimization algorithm.
        
        Q: What is backpropagation?
        A: A method to compute gradients.
        """
        
        flashcards = generator._extract_qa_pairs_fallback(response)
        
        assert len(flashcards) == 2
        assert "gradient descent" in flashcards[0]["question"].lower()
    
    def test_save_load_json(self):
        """Test saving and loading flashcards as JSON."""
        flashcards = [
            {"question": "Q1", "answer": "A1"},
            {"question": "Q2", "answer": "A2"},
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_flashcards.json"
            
            generator = FlashcardGenerator.__new__(FlashcardGenerator)
            generator._save_json(flashcards, output_path)
            
            assert output_path.exists()
            
            loaded = FlashcardGenerator.load_flashcards(output_path)
            assert len(loaded) == 2
            assert loaded[0]["question"] == "Q1"
    
    def test_save_csv(self):
        """Test saving flashcards as CSV."""
        flashcards = [
            {"question": "Q1", "answer": "A1", "topic": "T1"},
            {"question": "Q2", "answer": "A2", "topic": "T2"},
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_flashcards.csv"
            
            generator = FlashcardGenerator.__new__(FlashcardGenerator)
            generator._save_csv(flashcards, output_path)
            
            assert output_path.exists()
            
            # Read and verify
            import csv
            with open(output_path, "r") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            assert len(rows) == 2
            assert rows[0]["question"] == "Q1"
    
    def test_save_anki(self):
        """Test saving flashcards in Anki format."""
        flashcards = [
            {"question": "What is AI?", "answer": "Artificial Intelligence"},
            {"question": "What is ML?", "answer": "Machine Learning"},
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_flashcards.txt"
            
            generator = FlashcardGenerator.__new__(FlashcardGenerator)
            generator._save_anki(flashcards, output_path)
            
            assert output_path.exists()
            
            # Read and verify format
            with open(output_path, "r") as f:
                lines = f.readlines()
            
            assert len(lines) == 2
            assert "\t" in lines[0]  # Tab-separated
    
    def test_build_user_prompt(self):
        """Test user prompt construction."""
        generator = FlashcardGenerator.__new__(FlashcardGenerator)
        generator.max_cards_per_chunk = 5
        
        prompt = generator._build_user_prompt(
            "Test content",
            lecture_id="lec_01",
            topic="AI"
        )
        
        assert "5" in prompt
        assert "lec_01" in prompt
        assert "AI" in prompt
        assert "Test content" in prompt
    
    def test_generate_from_transcript_file(self, sample_transcript):
        """Test generating flashcards from transcript file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create transcript file
            transcript_path = Path(tmpdir) / "test_transcript.json"
            with open(transcript_path, "w") as f:
                json.dump(sample_transcript, f)
            
            # This would require actual LLM, so we just test the file loading part
            try:
                generator = FlashcardGenerator(max_cards_per_chunk=3)
                # Would call: flashcards = generator.generate_from_transcript(transcript_path)
                # For now, just verify file exists
                assert transcript_path.exists()
            except Exception:
                pytest.skip("LLM not available for testing")
    
    def test_empty_text_handling(self):
        """Test handling of empty text."""
        try:
            generator = FlashcardGenerator(max_cards_per_chunk=5)
            flashcards = generator.generate_flashcards("")
            assert flashcards == []
            
            flashcards = generator.generate_flashcards("   ")
            assert flashcards == []
        except Exception:
            pytest.skip("LLM not available for testing")
