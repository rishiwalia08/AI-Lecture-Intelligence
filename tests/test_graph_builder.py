"""
test_graph_builder.py
=====================
Unit tests for the GraphBuilder class.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.knowledge_graph.concept_extractor import ConceptExtractor
from src.knowledge_graph.graph_builder import GraphBuilder


@pytest.fixture
def builder():
    """Create a GraphBuilder instance."""
    return GraphBuilder()


@pytest.fixture
def extractor():
    """Create a ConceptExtractor instance."""
    return ConceptExtractor(model_name="en_core_web_sm")


class TestGraphBuilder:
    """Test suite for GraphBuilder."""
    
    def test_initialization(self, builder):
        """Test that builder initializes correctly."""
        assert builder.graph is not None
        assert builder.graph.number_of_nodes() == 0
        assert builder.graph.number_of_edges() == 0
    
    def test_add_concept(self, builder):
        """Test adding concepts to graph."""
        builder.add_concept("machine learning", "lecture_01")
        
        assert builder.graph.number_of_nodes() == 1
        assert builder.graph.has_node("machine learning")
        assert builder.concept_frequencies["machine learning"] == 1
        assert "lecture_01" in builder.lecture_references["machine learning"]
    
    def test_add_duplicate_concept(self, builder):
        """Test adding same concept multiple times."""
        builder.add_concept("neural network", "lecture_01")
        builder.add_concept("neural network", "lecture_02")
        
        assert builder.graph.number_of_nodes() == 1
        assert builder.concept_frequencies["neural network"] == 2
        assert len(builder.lecture_references["neural network"]) == 2
    
    def test_add_relationship(self, builder):
        """Test adding relationships between concepts."""
        builder.add_relationship("machine learning", "neural network")
        
        assert builder.graph.number_of_nodes() == 2
        assert builder.graph.number_of_edges() == 1
        assert builder.graph.has_edge("machine learning", "neural network")
    
    def test_add_relationship_with_weight(self, builder):
        """Test adding weighted relationships."""
        builder.add_relationship("ai", "ml", weight=2.0)
        
        edge_data = builder.graph.get_edge_data("ai", "ml")
        assert edge_data["weight"] == 2.0
    
    def test_build_from_concept_pairs(self, builder):
        """Test building graph from concept pairs."""
        pairs = [
            ("machine learning", "neural network"),
            ("neural network", "deep learning"),
            ("deep learning", "backpropagation"),
        ]
        
        builder.build_from_concept_pairs(pairs, "lecture_01")
        
        assert builder.graph.number_of_nodes() == 4
        assert builder.graph.number_of_edges() == 3
    
    def test_get_top_concepts(self, builder):
        """Test getting most frequent concepts."""
        builder.add_concept("ai", "lec1")
        builder.add_concept("ai", "lec2")
        builder.add_concept("ai", "lec3")
        builder.add_concept("ml", "lec1")
        builder.add_concept("ml", "lec2")
        builder.add_concept("dl", "lec1")
        
        top = builder.get_top_concepts(n=2)
        
        assert len(top) == 2
        assert top[0] == ("ai", 3)
        assert top[1] == ("ml", 2)
    
    def test_get_concept_neighbors(self, builder):
        """Test getting concept neighbors."""
        builder.add_relationship("ai", "ml")
        builder.add_relationship("ml", "dl")
        builder.add_relationship("dl", "ml")
        
        neighbors = builder.get_concept_neighbors("ml")
        
        assert "ai" in neighbors
        assert "dl" in neighbors
    
    def test_prune_graph(self, builder):
        """Test pruning low-frequency concepts."""
        builder.add_concept("frequent", "lec1")
        builder.add_concept("frequent", "lec2")
        builder.add_concept("frequent", "lec3")
        builder.add_concept("rare", "lec1")
        
        nodes_removed, _ = builder.prune_graph(min_frequency=2, min_degree=0)
        
        assert nodes_removed == 1
        assert builder.graph.has_node("frequent")
        assert not builder.graph.has_node("rare")
    
    def test_save_graph(self, builder):
        """Test saving graph to disk."""
        builder.add_concept("ai", "lec1")
        builder.add_concept("ml", "lec1")
        builder.add_relationship("ai", "ml")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_graph"
            builder.save_graph(output_path)
            
            assert (output_path.with_suffix(".graphml")).exists()
            assert (output_path.with_suffix(".json")).exists()
            assert (output_path.with_suffix(".csv")).exists()
    
    def test_get_statistics(self, builder):
        """Test getting graph statistics."""
        builder.add_concept("ai", "lec1")
        builder.add_concept("ml", "lec1")
        builder.add_relationship("ai", "ml")
        
        stats = builder.get_statistics()
        
        assert stats["num_concepts"] == 2
        assert stats["num_relationships"] == 1
        assert "avg_degree" in stats
        assert "density" in stats
    
    def test_build_from_transcript(self, builder, extractor):
        """Test building graph from transcript file."""
        transcript_data = {
            "text": "Machine learning uses neural networks for deep learning.",
            "segments": []
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            transcript_path = Path(tmpdir) / "test_transcript.json"
            with open(transcript_path, "w") as f:
                json.dump(transcript_data, f)
            
            count = builder.build_from_transcript(transcript_path, extractor)
            
            assert count > 0
            assert builder.graph.number_of_nodes() > 0
    
    def test_visualize(self, builder):
        """Test generating visualization."""
        builder.add_concept("ai", "lec1")
        builder.add_concept("ml", "lec1")
        builder.add_relationship("ai", "ml")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_graph.html"
            builder.visualize(output_path, max_nodes=10)
            
            assert output_path.exists()
            # Check that HTML contains PyVis content
            content = output_path.read_text()
            assert "network" in content.lower()
