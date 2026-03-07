#!/usr/bin/env python3
"""
build_concept_graph.py
======================
Pipeline script to build knowledge graph from lecture transcripts.

Usage:
    python scripts/build_concept_graph.py [--limit N] [--output-dir DIR]

Steps:
    1. Load transcript files
    2. Extract concepts using spaCy
    3. Build NetworkX graph
    4. Generate interactive PyVis visualization
    5. Save graph files and statistics
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

# Add project root to path
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

from src.knowledge_graph.concept_extractor import ConceptExtractor
from src.knowledge_graph.graph_builder import GraphBuilder
from src.utils.logger import get_logger

logger = get_logger(__name__)


def load_config(config_path: Path) -> dict:
    """Load configuration from YAML file."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def main():
    """Main pipeline execution."""
    parser = argparse.ArgumentParser(
        description="Build concept knowledge graph from lecture transcripts"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=_PROJECT_ROOT / "config" / "config.yaml",
        help="Path to configuration file",
    )
    parser.add_argument(
        "--transcripts-dir",
        type=Path,
        help="Directory containing transcript JSON files (overrides config)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for graph files (overrides config)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of transcripts to process",
    )
    parser.add_argument(
        "--max-viz-nodes",
        type=int,
        default=100,
        help="Maximum nodes in visualization (default: 100)",
    )
    parser.add_argument(
        "--min-frequency",
        type=int,
        default=2,
        help="Minimum concept frequency to keep (default: 2)",
    )
    parser.add_argument(
        "--spacy-model",
        type=str,
        default="en_core_web_trf",
        help="spaCy model to use (default: en_core_web_trf)",
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 70)
    logger.info("KNOWLEDGE GRAPH PIPELINE")
    logger.info("=" * 70)
    
    # Load configuration
    config = load_config(args.config)
    
    # Determine paths
    transcripts_dir = (
        args.transcripts_dir
        if args.transcripts_dir
        else _PROJECT_ROOT / config.get("transcripts_path", "data/transcripts")
    )
    
    output_dir = (
        args.output_dir
        if args.output_dir
        else _PROJECT_ROOT / config.get("knowledge_graph_output_path", "data/knowledge_graph")
    )
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Transcripts directory: {transcripts_dir}")
    logger.info(f"Output directory: {output_dir}")
    
    # Check if transcripts exist
    if not transcripts_dir.exists():
        logger.error(f"❌ Transcripts directory not found: {transcripts_dir}")
        logger.error("   Run Phase 2 ASR pipeline first: python scripts/run_phase2_asr.py")
        return 1
    
    transcript_files = list(transcripts_dir.glob("*.json"))
    if not transcript_files:
        logger.error(f"❌ No transcript files found in {transcripts_dir}")
        return 1
    
    logger.info(f"Found {len(transcript_files)} transcript files")
    
    # ─────────────────────────────────────────────────────────────
    # STEP 1: Initialize Concept Extractor
    # ─────────────────────────────────────────────────────────────
    logger.info("\n" + "─" * 70)
    logger.info("STEP 1: Initialize Concept Extractor")
    logger.info("─" * 70)
    
    try:
        extractor = ConceptExtractor(model_name=args.spacy_model)
    except OSError:
        logger.error(
            f"❌ spaCy model '{args.spacy_model}' not found.\n"
            f"   Install with: python -m spacy download {args.spacy_model}"
        )
        return 1
    
    # ─────────────────────────────────────────────────────────────
    # STEP 2: Build Knowledge Graph
    # ─────────────────────────────────────────────────────────────
    logger.info("\n" + "─" * 70)
    logger.info("STEP 2: Build Knowledge Graph")
    logger.info("─" * 70)
    
    builder = GraphBuilder()
    
    results = builder.build_from_transcripts(
        transcripts_dir,
        extractor,
        limit=args.limit,
    )
    
    total_concepts = sum(results.values())
    logger.info(f"\n✅ Extracted {total_concepts} total concepts")
    logger.info(f"✅ Unique concepts: {builder.graph.number_of_nodes()}")
    logger.info(f"✅ Relationships: {builder.graph.number_of_edges()}")
    
    # ─────────────────────────────────────────────────────────────
    # STEP 3: Prune Graph
    # ─────────────────────────────────────────────────────────────
    logger.info("\n" + "─" * 70)
    logger.info("STEP 3: Prune Low-Frequency Concepts")
    logger.info("─" * 70)
    
    nodes_removed, edges_removed = builder.prune_graph(
        min_frequency=args.min_frequency,
        min_degree=1,
    )
    
    logger.info(f"Removed {nodes_removed} low-frequency nodes")
    logger.info(f"Removed {edges_removed} edges")
    logger.info(f"Remaining nodes: {builder.graph.number_of_nodes()}")
    logger.info(f"Remaining edges: {builder.graph.number_of_edges()}")
    
    # ─────────────────────────────────────────────────────────────
    # STEP 4: Generate Statistics
    # ─────────────────────────────────────────────────────────────
    logger.info("\n" + "─" * 70)
    logger.info("STEP 4: Generate Statistics")
    logger.info("─" * 70)
    
    stats = builder.get_statistics()
    
    logger.info(f"\nGraph Statistics:")
    logger.info(f"  • Total concepts: {stats['num_concepts']}")
    logger.info(f"  • Total relationships: {stats['num_relationships']}")
    logger.info(f"  • Average degree: {stats['avg_degree']:.2f}")
    logger.info(f"  • Graph density: {stats['density']:.4f}")
    logger.info(f"  • Connected components: {stats['num_weakly_connected_components']}")
    
    logger.info(f"\nTop 10 Most Frequent Concepts:")
    for i, (concept, freq) in enumerate(stats['top_concepts'], 1):
        logger.info(f"  {i:2d}. {concept:30s} (freq: {freq})")
    
    logger.info(f"\nTop 10 Most Central Concepts (PageRank):")
    for i, (concept, score) in enumerate(stats['central_concepts'], 1):
        logger.info(f"  {i:2d}. {concept:30s} (score: {score:.4f})")
    
    # ─────────────────────────────────────────────────────────────
    # STEP 5: Save Graph Files
    # ─────────────────────────────────────────────────────────────
    logger.info("\n" + "─" * 70)
    logger.info("STEP 5: Save Graph Files")
    logger.info("─" * 70)
    
    graph_base_path = output_dir / "concept_graph"
    builder.save_graph(graph_base_path)
    
    # ─────────────────────────────────────────────────────────────
    # STEP 6: Generate Interactive Visualization
    # ─────────────────────────────────────────────────────────────
    logger.info("\n" + "─" * 70)
    logger.info("STEP 6: Generate Interactive Visualization")
    logger.info("─" * 70)
    
    viz_path = _PROJECT_ROOT / "frontend" / "concept_graph.html"
    
    builder.visualize(
        output_path=viz_path,
        title="Interactive Lecture Concept Knowledge Graph",
        max_nodes=args.max_viz_nodes,
    )
    
    logger.info(f"\n{'=' * 70}")
    logger.info("✅ PIPELINE COMPLETE")
    logger.info(f"{'=' * 70}")
    logger.info(f"\nOutputs:")
    logger.info(f"  • Graph (GraphML): {graph_base_path}.graphml")
    logger.info(f"  • Graph (JSON):    {graph_base_path}.json")
    logger.info(f"  • Statistics CSV:  {graph_base_path}.csv")
    logger.info(f"  • Visualization:   {viz_path}")
    logger.info(f"\nOpen the visualization in your browser:")
    logger.info(f"  file://{viz_path.absolute()}")
    logger.info("")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
