"""
test_lecture_summarizer.py
===========================
Unit tests for lecture summarizer module.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.education.lecture_summarizer import LectureSummarizer


@pytest.fixture
def mock_llm():
    """Create mock LLM."""
    llm = Mock()
    llm.generate = Mock(return_value='{"summary": "Test summary", "key_concepts": ["concept1"], "definitions": {}}')
    return llm


@pytest.fixture
def summarizer(mock_llm):
    """Create summarizer with mocked LLM."""
    with patch('src.education.lecture_summarizer.load_llm', return_value=mock_llm):
        return LectureSummarizer(chunk_size=100, chunk_overlap=20)


@pytest.fixture
def sample_text():
    """Sample lecture text."""
    return (
        "Neural networks are computational models inspired by biological neurons. "
        "They consist of layers of interconnected nodes. Each node performs a simple "
        "computation. Deep learning uses multiple layers to learn hierarchical representations. "
        "Backpropagation is the algorithm used to train neural networks by computing gradients."
    )


@pytest.fixture
def sample_transcript_data():
    """Sample transcript JSON data."""
    return {
        "lecture_id": "lecture_01",
        "topic": "Neural Networks",
        "text": "Neural networks are models. They learn patterns.",
        "segments": [
            {"text": "Neural networks are models.", "start": 0, "end": 5},
            {"text": "They learn patterns.", "start": 5, "end": 10},
        ]
    }


@pytest.fixture
def temp_transcript_file(tmp_path, sample_transcript_data):
    """Create temporary transcript file."""
    transcript_path = tmp_path / "lecture_01_transcript.json"
    with open(transcript_path, "w", encoding="utf-8") as f:
        json.dump(sample_transcript_data, f)
    return transcript_path


class TestLectureSummarizer:
    """Test LectureSummarizer class."""
    
    def test_initialization(self, mock_llm):
        """Test summarizer initialization."""
        with patch('src.education.lecture_summarizer.load_llm', return_value=mock_llm):
            summarizer = LectureSummarizer(chunk_size=1000, chunk_overlap=100)
            
            assert summarizer.chunk_size == 1000
            assert summarizer.chunk_overlap == 100
            assert summarizer.llm == mock_llm
    
    def test_split_into_chunks(self, summarizer):
        """Test text chunking."""
        text = "This is sentence one. This is sentence two. This is sentence three. This is sentence four."
        
        chunks = summarizer._split_into_chunks(text)
        
        assert len(chunks) > 0
        # Check overlap
        if len(chunks) > 1:
            # Some overlap should exist
            assert len(chunks[0]) + len(chunks[1]) > len(text)
    
    def test_split_into_chunks_short_text(self, summarizer):
        """Test chunking with text shorter than chunk size."""
        text = "Short text."
        
        chunks = summarizer._split_into_chunks(text)
        
        assert len(chunks) == 1
        assert chunks[0] == text
    
    def test_summarize_chunk(self, summarizer, mock_llm):
        """Test chunk summarization."""
        chunk = "This is a test chunk of text."
        mock_llm.generate.return_value = "Summary of test chunk."
        
        summary = summarizer._summarize_chunk(chunk)
        
        assert summary == "Summary of test chunk."
        mock_llm.generate.assert_called_once()
        
        # Check system prompt
        call_args = mock_llm.generate.call_args[0][0]
        assert call_args[0]["role"] == "system"
        assert "summarize" in call_args[0]["content"].lower()
    
    def test_parse_summary_response_valid_json(self, summarizer):
        """Test parsing valid JSON response."""
        response = '{"summary": "Test summary", "key_concepts": ["concept1", "concept2"], "definitions": {"term1": "def1"}}'
        
        result = summarizer._parse_summary_response(response)
        
        assert result["summary"] == "Test summary"
        assert result["key_concepts"] == ["concept1", "concept2"]
        assert result["definitions"] == {"term1": "def1"}
    
    def test_parse_summary_response_embedded_json(self, summarizer):
        """Test parsing JSON embedded in text."""
        response = 'Here is the summary: {"summary": "Test", "key_concepts": [], "definitions": {}} done'
        
        result = summarizer._parse_summary_response(response)
        
        assert result["summary"] == "Test"
        assert result["key_concepts"] == []
        assert result["definitions"] == {}
    
    def test_parse_summary_response_invalid_json(self, summarizer):
        """Test fallback parsing for invalid JSON."""
        response = "This is just a plain text summary without JSON."
        
        result = summarizer._parse_summary_response(response)
        
        assert "This is just a plain text summary" in result["summary"]
        assert isinstance(result["key_concepts"], list)
        assert isinstance(result["definitions"], dict)
    
    def test_extract_summary_fallback(self, summarizer):
        """Test fallback summary extraction."""
        response = """
        This is the main summary paragraph about neural networks.
        
        Key Concepts:
        - Neural networks
        - Deep learning
        - Backpropagation
        """
        
        result = summarizer._extract_summary_fallback(response)
        
        assert "neural networks" in result["summary"].lower()
        assert len(result["key_concepts"]) > 0
    
    def test_combine_summaries(self, summarizer, mock_llm):
        """Test combining chunk summaries."""
        chunk_summaries = [
            "Summary of part 1.",
            "Summary of part 2.",
            "Summary of part 3.",
        ]
        mock_llm.generate.return_value = '{"summary": "Combined summary", "key_concepts": ["key1"], "definitions": {}}'
        
        result = summarizer._combine_summaries(chunk_summaries, topic="Test Topic")
        
        assert result["summary"] == "Combined summary"
        assert "key1" in result["key_concepts"]
        mock_llm.generate.assert_called()
    
    def test_summarize_lecture(self, summarizer, sample_text, mock_llm):
        """Test full lecture summarization."""
        mock_llm.generate.side_effect = [
            "Chunk summary 1",
            "Chunk summary 2",
            '{"summary": "Final summary", "key_concepts": ["neural networks"], "definitions": {"NN": "Neural Network"}}'
        ]
        
        result = summarizer.summarize_lecture(
            sample_text,
            lecture_id="lecture_01",
            topic="Neural Networks"
        )
        
        assert "summary" in result
        assert "key_concepts" in result
        assert "definitions" in result
        assert result.get("lecture_id") == "lecture_01"
        assert result.get("topic") == "Neural Networks"
    
    def test_summarize_lecture_empty_text(self, summarizer):
        """Test summarization with empty text."""
        result = summarizer.summarize_lecture("")
        
        assert result["summary"] == ""
        assert result["key_concepts"] == []
        assert result["definitions"] == {}
    
    def test_summarize_from_transcript(self, summarizer, temp_transcript_file, mock_llm):
        """Test summarization from transcript file."""
        mock_llm.generate.side_effect = [
            "Chunk summary",
            '{"summary": "Lecture summary", "key_concepts": ["networks"], "definitions": {}}'
        ]
        
        result = summarizer.summarize_from_transcript(temp_transcript_file)
        
        assert "summary" in result
        assert result.get("lecture_id", "").startswith("lecture")
    
    def test_summarize_from_transcript_segments(self, summarizer, tmp_path, mock_llm):
        """Test summarization from transcript with segments."""
        transcript_data = {
            "lecture_id": "lecture_02",
            "segments": [
                {"text": "First segment.", "start": 0, "end": 5},
                {"text": "Second segment.", "start": 5, "end": 10},
            ]
        }
        transcript_path = tmp_path / "lecture_02_transcript.json"
        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump(transcript_data, f)
        
        mock_llm.generate.side_effect = [
            "Summary",
            '{"summary": "Combined", "key_concepts": [], "definitions": {}}'
        ]
        
        result = summarizer.summarize_from_transcript(transcript_path)
        
        assert "summary" in result
    
    def test_summarize_from_transcripts_batch(self, summarizer, tmp_path, mock_llm):
        """Test batch summarization."""
        # Create multiple transcript files
        for i in range(3):
            transcript_data = {
                "lecture_id": f"lecture_{i:02d}",
                "text": f"This is lecture {i} content.",
            }
            transcript_path = tmp_path / f"lecture_{i:02d}_transcript.json"
            with open(transcript_path, "w", encoding="utf-8") as f:
                json.dump(transcript_data, f)
        
        mock_llm.generate.side_effect = [
            "Chunk1", '{"summary": "S1", "key_concepts": [], "definitions": {}}',
            "Chunk2", '{"summary": "S2", "key_concepts": [], "definitions": {}}',
            "Chunk3", '{"summary": "S3", "key_concepts": [], "definitions": {}}',
        ]
        
        results = summarizer.summarize_from_transcripts(tmp_path, limit=3)
        
        assert len(results) == 3
        assert "lecture_00" in results
        assert "lecture_01" in results
        assert "lecture_02" in results
    
    def test_save_and_load_summary(self, summarizer, tmp_path):
        """Test saving and loading summary."""
        summary = {
            "summary": "Test summary",
            "key_concepts": ["concept1", "concept2"],
            "definitions": {"term1": "definition1"},
            "lecture_id": "lecture_01",
        }
        
        output_path = tmp_path / "test_summary.json"
        summarizer.save_summary(summary, output_path)
        
        assert output_path.exists()
        
        # Load and verify
        loaded = LectureSummarizer.load_summary(output_path)
        assert loaded["summary"] == "Test summary"
        assert len(loaded["key_concepts"]) == 2
        assert loaded["definitions"]["term1"] == "definition1"
    
    def test_load_summary_nonexistent(self, tmp_path):
        """Test loading nonexistent summary."""
        result = LectureSummarizer.load_summary(tmp_path / "nonexistent.json")
        
        assert result["summary"] == ""
        assert result["key_concepts"] == []
        assert result["definitions"] == {}
    
    def test_empty_summary(self, summarizer):
        """Test empty summary structure."""
        result = summarizer._empty_summary()
        
        assert result["summary"] == ""
        assert result["key_concepts"] == []
        assert result["definitions"] == {}
