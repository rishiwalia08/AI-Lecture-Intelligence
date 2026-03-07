"""
graph_builder.py
================
Build and visualize knowledge graphs from extracted concepts using NetworkX and PyVis.

Constructs directed graphs where:
- Nodes represent concepts
- Edges represent co-occurrence relationships
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
import pandas as pd
from pyvis.network import Network

from src.utils.logger import get_logger

logger = get_logger(__name__)


class GraphBuilder:
    """
    Build and manage knowledge graphs from lecture concepts.
    
    Attributes:
        graph: NetworkX directed graph
        concept_frequencies: Dictionary tracking concept occurrence counts
        edge_weights: Dictionary tracking edge weights (co-occurrences)
        lecture_references: Dictionary mapping concepts to lecture sources
    """
    
    def __init__(self):
        """Initialize an empty knowledge graph."""
        self.graph = nx.DiGraph()
        self.concept_frequencies: Dict[str, int] = defaultdict(int)
        self.edge_weights: Dict[Tuple[str, str], int] = defaultdict(int)
        self.lecture_references: Dict[str, Set[str]] = defaultdict(set)
        logger.info("Initialized empty knowledge graph")
    
    def add_concept(self, concept: str, lecture_id: str = "") -> None:
        """
        Add a concept node to the graph.
        
        Args:
            concept: Concept name
            lecture_id: Optional lecture identifier for reference tracking
        """
        if not concept:
            return
        
        concept = concept.lower().strip()
        self.concept_frequencies[concept] += 1
        
        if lecture_id:
            self.lecture_references[concept].add(lecture_id)
        
        # Add or update node
        if self.graph.has_node(concept):
            self.graph.nodes[concept]["frequency"] += 1
        else:
            self.graph.add_node(
                concept,
                frequency=1,
                lectures=list(self.lecture_references[concept])
            )
    
    def add_relationship(
        self, concept1: str, concept2: str, weight: float = 1.0
    ) -> None:
        """
        Add a relationship edge between two concepts.
        
        Args:
            concept1: Source concept
            concept2: Target concept
            weight: Edge weight (default: 1.0)
        """
        if not concept1 or not concept2 or concept1 == concept2:
            return
        
        concept1 = concept1.lower().strip()
        concept2 = concept2.lower().strip()
        
        # Ensure both nodes exist
        if not self.graph.has_node(concept1):
            self.add_concept(concept1)
        if not self.graph.has_node(concept2):
            self.add_concept(concept2)
        
        # Add or update edge
        if self.graph.has_edge(concept1, concept2):
            self.graph[concept1][concept2]["weight"] += weight
        else:
            self.graph.add_edge(concept1, concept2, weight=weight)
        
        self.edge_weights[(concept1, concept2)] += 1
    
    def build_from_concept_pairs(
        self, concept_pairs: List[Tuple[str, str]], lecture_id: str = ""
    ) -> None:
        """
        Build graph from a list of concept pairs.
        
        Args:
            concept_pairs: List of (concept1, concept2) tuples
            lecture_id: Optional lecture identifier
        """
        for concept1, concept2 in concept_pairs:
            self.add_concept(concept1, lecture_id)
            self.add_concept(concept2, lecture_id)
            self.add_relationship(concept1, concept2)
    
    def build_from_transcript(
        self,
        transcript_path: Path,
        concept_extractor: Any,
        lecture_id: Optional[str] = None,
    ) -> int:
        """
        Build graph from a single transcript file.
        
        Args:
            transcript_path: Path to transcript JSON file
            concept_extractor: ConceptExtractor instance
            lecture_id: Optional lecture identifier (defaults to filename)
            
        Returns:
            Number of concepts extracted
        """
        if lecture_id is None:
            lecture_id = transcript_path.stem
        
        logger.info(f"Processing transcript: {transcript_path.name}")
        
        try:
            with open(transcript_path, "r", encoding="utf-8") as f:
                transcript_data = json.load(f)
            
            # Extract full text from transcript
            if "text" in transcript_data:
                text = transcript_data["text"]
            elif "segments" in transcript_data:
                text = " ".join(seg.get("text", "") for seg in transcript_data["segments"])
            else:
                logger.warning(f"No text found in {transcript_path.name}")
                return 0
            
            # Extract concept pairs
            concept_pairs = concept_extractor.extract_concept_pairs(text)
            
            # Also extract individual concepts
            concepts = concept_extractor.extract_concepts(text)
            for concept in concepts:
                self.add_concept(concept, lecture_id)
            
            # Build relationships
            self.build_from_concept_pairs(concept_pairs, lecture_id)
            
            logger.info(f"✅ Extracted {len(concepts)} concepts from {lecture_id}")
            return len(concepts)
            
        except Exception as e:
            logger.error(f"Error processing {transcript_path.name}: {e}")
            return 0
    
    def build_from_transcripts(
        self,
        transcript_dir: Path,
        concept_extractor: Any,
        limit: Optional[int] = None,
    ) -> Dict[str, int]:
        """
        Build graph from multiple transcript files.
        
        Args:
            transcript_dir: Directory containing transcript JSON files
            concept_extractor: ConceptExtractor instance
            limit: Optional limit on number of files to process
            
        Returns:
            Dictionary mapping lecture_id to concept count
        """
        transcript_files = sorted(transcript_dir.glob("*.json"))
        
        if limit:
            transcript_files = transcript_files[:limit]
        
        logger.info(f"Processing {len(transcript_files)} transcript files...")
        
        results = {}
        for transcript_path in transcript_files:
            lecture_id = transcript_path.stem
            count = self.build_from_transcript(
                transcript_path, concept_extractor, lecture_id
            )
            results[lecture_id] = count
        
        logger.info(f"✅ Built graph with {self.graph.number_of_nodes()} concepts")
        logger.info(f"✅ Created {self.graph.number_of_edges()} relationships")
        
        return results
    
    def get_top_concepts(self, n: int = 20) -> List[Tuple[str, int]]:
        """
        Get the top N most frequent concepts.
        
        Args:
            n: Number of top concepts to return
            
        Returns:
            List of (concept, frequency) tuples
        """
        sorted_concepts = sorted(
            self.concept_frequencies.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_concepts[:n]
    
    def get_concept_neighbors(self, concept: str) -> List[str]:
        """
        Get all concepts directly connected to a given concept.
        
        Args:
            concept: Concept to find neighbors for
            
        Returns:
            List of neighbor concepts
        """
        concept = concept.lower().strip()
        if not self.graph.has_node(concept):
            return []
        
        # Get both predecessors and successors
        neighbors = set(self.graph.predecessors(concept))
        neighbors.update(self.graph.successors(concept))
        
        return sorted(list(neighbors))
    
    def get_central_concepts(self, n: int = 10) -> List[Tuple[str, float]]:
        """
        Get the most central concepts using PageRank algorithm.
        
        Args:
            n: Number of central concepts to return
            
        Returns:
            List of (concept, centrality_score) tuples
        """
        if self.graph.number_of_nodes() == 0:
            return []
        
        pagerank = nx.pagerank(self.graph)
        sorted_concepts = sorted(
            pagerank.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_concepts[:n]
    
    def prune_graph(
        self, min_frequency: int = 2, min_degree: int = 1
    ) -> Tuple[int, int]:
        """
        Remove low-frequency concepts and isolated nodes.
        
        Args:
            min_frequency: Minimum concept frequency to keep
            min_degree: Minimum node degree (connections) to keep
            
        Returns:
            Tuple of (nodes_removed, edges_removed)
        """
        nodes_to_remove = []
        
        for node in self.graph.nodes():
            frequency = self.graph.nodes[node].get("frequency", 0)
            degree = self.graph.degree(node)
            
            if frequency < min_frequency or degree < min_degree:
                nodes_to_remove.append(node)
        
        initial_nodes = self.graph.number_of_nodes()
        initial_edges = self.graph.number_of_edges()
        
        self.graph.remove_nodes_from(nodes_to_remove)
        
        nodes_removed = initial_nodes - self.graph.number_of_nodes()
        edges_removed = initial_edges - self.graph.number_of_edges()
        
        logger.info(f"Pruned {nodes_removed} nodes and {edges_removed} edges")
        
        return nodes_removed, edges_removed
    
    def save_graph(self, output_path: Path) -> None:
        """
        Save graph to disk in multiple formats.
        
        Args:
            output_path: Base path for output files (without extension)
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save as GraphML (preserves all attributes)
        graphml_path = output_path.with_suffix(".graphml")
        nx.write_graphml(self.graph, graphml_path)
        logger.info(f"💾 Saved GraphML to {graphml_path}")
        
        # Save as JSON (edge list)
        json_path = output_path.with_suffix(".json")
        graph_data = {
            "nodes": [
                {
                    "id": node,
                    "frequency": self.graph.nodes[node].get("frequency", 1),
                    "lectures": list(self.lecture_references.get(node, [])),
                }
                for node in self.graph.nodes()
            ],
            "edges": [
                {
                    "source": u,
                    "target": v,
                    "weight": self.graph[u][v].get("weight", 1),
                }
                for u, v in self.graph.edges()
            ],
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(graph_data, f, indent=2)
        logger.info(f"💾 Saved JSON to {json_path}")
        
        # Save statistics as CSV
        csv_path = output_path.with_suffix(".csv")
        stats_data = []
        for node in self.graph.nodes():
            stats_data.append({
                "concept": node,
                "frequency": self.graph.nodes[node].get("frequency", 1),
                "degree": self.graph.degree(node),
                "in_degree": self.graph.in_degree(node),
                "out_degree": self.graph.out_degree(node),
                "num_lectures": len(self.lecture_references.get(node, [])),
            })
        df = pd.DataFrame(stats_data)
        df.to_csv(csv_path, index=False)
        logger.info(f"💾 Saved statistics to {csv_path}")
    
    def visualize(
        self,
        output_path: Path,
        title: str = "Lecture Concept Knowledge Graph",
        max_nodes: Optional[int] = 100,
        height: str = "800px",
        width: str = "100%",
    ) -> None:
        """
        Create an interactive HTML visualization using PyVis.
        
        Args:
            output_path: Path to output HTML file
            title: Graph title
            max_nodes: Maximum number of nodes to display (shows most central)
            height: Graph height (CSS format)
            width: Graph width (CSS format)
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Select subgraph if needed
        if max_nodes and self.graph.number_of_nodes() > max_nodes:
            logger.info(f"Limiting visualization to {max_nodes} most central concepts")
            central_concepts = self.get_central_concepts(max_nodes)
            nodes_to_show = [concept for concept, _ in central_concepts]
            subgraph = self.graph.subgraph(nodes_to_show)
        else:
            subgraph = self.graph
        
        # Create PyVis network
        net = Network(
            height=height,
            width=width,
            bgcolor="#ffffff",
            font_color="#000000",
            directed=True,
        )
        
        net.barnes_hut(
            gravity=-8000,
            central_gravity=0.3,
            spring_length=200,
            spring_strength=0.001,
            damping=0.09,
        )
        
        # Add nodes with size based on frequency
        for node in subgraph.nodes():
            frequency = subgraph.nodes[node].get("frequency", 1)
            lectures = self.lecture_references.get(node, set())
            
            # Node size based on frequency
            size = min(10 + frequency * 3, 50)
            
            # Node color based on degree
            degree = subgraph.degree(node)
            if degree > 5:
                color = "#ff6b6b"  # Red for highly connected
            elif degree > 2:
                color = "#4ecdc4"  # Teal for moderately connected
            else:
                color = "#95a5a6"  # Gray for sparsely connected
            
            # Node title (hover text)
            title_text = f"<b>{node.title()}</b><br>"
            title_text += f"Frequency: {frequency}<br>"
            title_text += f"Connections: {degree}<br>"
            title_text += f"Lectures: {len(lectures)}"
            
            net.add_node(
                node,
                label=node.title(),
                title=title_text,
                size=size,
                color=color,
            )
        
        # Add edges with width based on weight
        for u, v in subgraph.edges():
            weight = subgraph[u][v].get("weight", 1)
            width = min(1 + weight * 0.5, 5)
            
            net.add_edge(
                u,
                v,
                width=width,
                title=f"Co-occurrence: {weight}",
                arrows="to",
            )
        
        # Set options
        net.set_options("""
        {
          "nodes": {
            "font": {
              "size": 14,
              "face": "Arial"
            },
            "borderWidth": 2,
            "borderWidthSelected": 4
          },
          "edges": {
            "color": {
              "inherit": false,
              "color": "#848484",
              "highlight": "#000000"
            },
            "smooth": {
              "type": "continuous"
            }
          },
          "physics": {
            "enabled": true,
            "stabilization": {
              "iterations": 200
            }
          },
          "interaction": {
            "hover": true,
            "navigationButtons": true,
            "keyboard": true,
            "tooltipDelay": 100
          }
        }
        """)
        
        # Save visualization
        net.save_graph(str(output_path))
        logger.info(f"🎨 Saved interactive visualization to {output_path}")
        logger.info(f"   Nodes: {subgraph.number_of_nodes()}")
        logger.info(f"   Edges: {subgraph.number_of_edges()}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get graph statistics.
        
        Returns:
            Dictionary of statistics
        """
        if self.graph.number_of_nodes() == 0:
            return {"error": "Empty graph"}
        
        return {
            "num_concepts": self.graph.number_of_nodes(),
            "num_relationships": self.graph.number_of_edges(),
            "avg_degree": sum(dict(self.graph.degree()).values()) / self.graph.number_of_nodes(),
            "density": nx.density(self.graph),
            "num_weakly_connected_components": nx.number_weakly_connected_components(self.graph),
            "top_concepts": self.get_top_concepts(10),
            "central_concepts": self.get_central_concepts(10),
        }
