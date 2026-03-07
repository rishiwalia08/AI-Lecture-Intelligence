#!/usr/bin/env python3
"""
generate_flashcards.py
======================
Pipeline script to generate study flashcards from lecture transcripts.

Usage:
    python scripts/generate_flashcards.py [--limit N] [--output-dir DIR]

Steps:
    1. Load transcript files
    2. Generate flashcards using LLM
    3. Save in multiple formats (JSON, CSV, Anki)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

# Add project root to path
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

from src.education.flashcard_generator import FlashcardGenerator
from src.utils.logger import get_logger

logger = get_logger(__name__)


def load_config(config_path: Path) -> dict:
    """Load configuration from YAML file."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def main():
    """Main pipeline execution."""
    parser = argparse.ArgumentParser(
        description="Generate study flashcards from lecture transcripts"
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
        help="Output directory for flashcards (overrides config)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of transcripts to process",
    )
    parser.add_argument(
        "--max-cards",
        type=int,
        default=10,
        help="Maximum flashcards per transcript (default: 10)",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=["json", "csv", "anki"],
        default=["json"],
        help="Output formats (default: json)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["ollama", "groq"],
        help="LLM provider (overrides config)",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="LLM model name (overrides config)",
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 70)
    logger.info("FLASHCARD GENERATION PIPELINE")
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
        else _PROJECT_ROOT / config.get("flashcards_path", "data/flashcards")
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
    # STEP 1: Initialize Flashcard Generator
    # ─────────────────────────────────────────────────────────────
    logger.info("\n" + "─" * 70)
    logger.info("STEP 1: Initialize Flashcard Generator")
    logger.info("─" * 70)
    
    # Build LLM config
    llm_config = config.get("llm", {})
    if args.provider:
        llm_config["provider"] = args.provider
    if args.model:
        llm_config["model"] = args.model
    
    logger.info(f"LLM Provider: {llm_config.get('provider', 'ollama')}")
    logger.info(f"LLM Model: {llm_config.get('model', 'llama3')}")
    
    try:
        generator = FlashcardGenerator(
            model_config=llm_config,
            max_cards_per_chunk=args.max_cards,
        )
    except Exception as e:
        logger.error(f"❌ Failed to initialize generator: {e}")
        return 1
    
    # ─────────────────────────────────────────────────────────────
    # STEP 2: Generate Flashcards
    # ─────────────────────────────────────────────────────────────
    logger.info("\n" + "─" * 70)
    logger.info("STEP 2: Generate Flashcards from Transcripts")
    logger.info("─" * 70)
    
    all_flashcards = generator.generate_from_transcripts(
        transcripts_dir,
        limit=args.limit,
    )
    
    if not all_flashcards:
        logger.error("❌ No flashcards generated")
        return 1
    
    total_cards = sum(len(cards) for cards in all_flashcards.values())
    logger.info(f"\n✅ Generated {total_cards} total flashcards from {len(all_flashcards)} lectures")
    
    # ─────────────────────────────────────────────────────────────
    # STEP 3: Save Flashcards
    # ─────────────────────────────────────────────────────────────
    logger.info("\n" + "─" * 70)
    logger.info("STEP 3: Save Flashcards")
    logger.info("─" * 70)
    
    for lecture_id, flashcards in all_flashcards.items():
        logger.info(f"\nSaving flashcards for {lecture_id}...")
        
        for fmt in args.formats:
            if fmt == "json":
                output_path = output_dir / f"{lecture_id}_flashcards.json"
            elif fmt == "csv":
                output_path = output_dir / f"{lecture_id}_flashcards.csv"
            elif fmt == "anki":
                output_path = output_dir / f"{lecture_id}_flashcards.txt"
            
            try:
                generator.save_flashcards(flashcards, output_path, format=fmt)
            except Exception as e:
                logger.error(f"❌ Error saving {fmt} format: {e}")
    
    # Save combined flashcards
    logger.info("\nSaving combined flashcards...")
    all_cards_flat = []
    for cards in all_flashcards.values():
        all_cards_flat.extend(cards)
    
    for fmt in args.formats:
        if fmt == "json":
            combined_path = output_dir / "all_flashcards.json"
        elif fmt == "csv":
            combined_path = output_dir / "all_flashcards.csv"
        elif fmt == "anki":
            combined_path = output_dir / "all_flashcards.txt"
        
        try:
            generator.save_flashcards(all_cards_flat, combined_path, format=fmt)
        except Exception as e:
            logger.error(f"❌ Error saving combined {fmt}: {e}")
    
    # ─────────────────────────────────────────────────────────────
    # STEP 4: Summary
    # ─────────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 70)
    logger.info("✅ PIPELINE COMPLETE")
    logger.info("=" * 70)
    
    logger.info(f"\nStatistics:")
    logger.info(f"  • Total lectures: {len(all_flashcards)}")
    logger.info(f"  • Total flashcards: {total_cards}")
    logger.info(f"  • Average per lecture: {total_cards / len(all_flashcards):.1f}")
    logger.info(f"  • Output formats: {', '.join(args.formats)}")
    
    logger.info(f"\nOutputs:")
    logger.info(f"  • Individual files: {output_dir}/<lecture_id>_flashcards.*")
    logger.info(f"  • Combined file: {output_dir}/all_flashcards.*")
    
    logger.info(f"\nNext steps:")
    logger.info(f"  1. Review flashcards: cat {output_dir}/all_flashcards.json | jq")
    logger.info(f"  2. Import to Anki: {output_dir}/all_flashcards.txt")
    logger.info(f"  3. Study in UI: streamlit run frontend/streamlit_app.py")
    logger.info("")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
