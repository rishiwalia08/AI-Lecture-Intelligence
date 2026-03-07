"""
generate_summaries.py
=====================
Pipeline script to generate lecture summaries from transcripts.

Usage:
    python scripts/generate_summaries.py
    python scripts/generate_summaries.py --limit 5
    python scripts/generate_summaries.py --transcript data/transcripts/lecture_01_transcript.json
"""

import argparse
import sys
from pathlib import Path

import yaml

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.education.lecture_summarizer import LectureSummarizer
from src.utils.logger import get_logger

logger = get_logger(__name__)


def load_config() -> dict:
    """Load configuration from YAML file."""
    config_path = project_root / "config" / "config.yaml"
    
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        return {}
    
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    return config


def generate_summaries(
    transcript_dir: Path,
    output_dir: Path,
    config: dict,
    limit: int = None,
    single_transcript: Path = None,
):
    """
    Generate summaries from transcripts.
    
    Args:
        transcript_dir: Directory containing transcript files
        output_dir: Directory to save summaries
        config: Configuration dictionary
        limit: Optional limit on number of files
        single_transcript: Optional path to single transcript file
    """
    logger.info("=" * 60)
    logger.info("LECTURE SUMMARIZATION PIPELINE")
    logger.info("=" * 60)
    
    # Get LLM config
    llm_config = config.get("llm", {})
    summary_config = config.get("summaries", {})
    
    chunk_size = summary_config.get("chunk_size", 2000)
    chunk_overlap = summary_config.get("chunk_overlap", 200)
    
    # Initialize summarizer
    logger.info("\n📚 Initializing lecture summarizer...")
    summarizer = LectureSummarizer(
        model_config=llm_config,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process single transcript or batch
    if single_transcript:
        logger.info(f"\n📄 Processing single transcript: {single_transcript.name}")
        summary = summarizer.summarize_from_transcript(single_transcript)
        
        # Save summary
        output_file = output_dir / f"{single_transcript.stem.replace('_transcript', '')}_summary.json"
        summarizer.save_summary(summary, output_file)
        
        # Print summary
        print_summary_info(single_transcript.stem, summary)
        
    else:
        logger.info(f"\n📄 Processing transcripts from: {transcript_dir}")
        if limit:
            logger.info(f"   Limit: {limit} files")
        
        # Process batch
        summaries = summarizer.summarize_from_transcripts(
            transcript_dir,
            limit=limit,
        )
        
        # Save summaries
        logger.info(f"\n💾 Saving summaries to: {output_dir}")
        for lecture_id, summary in summaries.items():
            output_file = output_dir / f"{lecture_id}_summary.json"
            summarizer.save_summary(summary, output_file)
        
        # Print statistics
        print_batch_statistics(summaries)
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ SUMMARIZATION COMPLETE")
    logger.info("=" * 60)


def print_summary_info(lecture_id: str, summary: dict):
    """Print summary information."""
    print("\n" + "=" * 60)
    print(f"SUMMARY: {lecture_id}")
    print("=" * 60)
    
    # Summary
    summary_text = summary.get("summary", "")
    if summary_text:
        print(f"\n📝 Summary ({len(summary_text)} chars):")
        print("-" * 60)
        # Print first 500 characters
        preview = summary_text[:500]
        if len(summary_text) > 500:
            preview += "..."
        print(preview)
    
    # Key concepts
    key_concepts = summary.get("key_concepts", [])
    if key_concepts:
        print(f"\n🔑 Key Concepts ({len(key_concepts)}):")
        print("-" * 60)
        for i, concept in enumerate(key_concepts, 1):
            print(f"  {i}. {concept}")
    
    # Definitions
    definitions = summary.get("definitions", {})
    if definitions:
        print(f"\n📖 Definitions ({len(definitions)}):")
        print("-" * 60)
        for term, definition in list(definitions.items())[:5]:  # Show first 5
            print(f"  • {term}: {definition}")
        if len(definitions) > 5:
            print(f"  ... and {len(definitions) - 5} more")


def print_batch_statistics(summaries: dict):
    """Print batch processing statistics."""
    print("\n" + "=" * 60)
    print("BATCH STATISTICS")
    print("=" * 60)
    
    total = len(summaries)
    print(f"\n📊 Total summaries: {total}")
    
    if total == 0:
        return
    
    # Analyze summaries
    total_summary_length = 0
    total_concepts = 0
    total_definitions = 0
    
    for summary in summaries.values():
        total_summary_length += len(summary.get("summary", ""))
        total_concepts += len(summary.get("key_concepts", []))
        total_definitions += len(summary.get("definitions", {}))
    
    avg_summary_length = total_summary_length / total
    avg_concepts = total_concepts / total
    avg_definitions = total_definitions / total
    
    print(f"\n📏 Average summary length: {avg_summary_length:.0f} characters")
    print(f"🔑 Average key concepts: {avg_concepts:.1f} per lecture")
    print(f"📖 Average definitions: {avg_definitions:.1f} per lecture")
    
    print(f"\n📈 Totals:")
    print(f"   Total key concepts: {total_concepts}")
    print(f"   Total definitions: {total_definitions}")
    
    # List lecture IDs
    print(f"\n📚 Lectures summarized:")
    for i, lecture_id in enumerate(sorted(summaries.keys()), 1):
        concepts_count = len(summaries[lecture_id].get("key_concepts", []))
        print(f"   {i}. {lecture_id} ({concepts_count} key concepts)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate lecture summaries from transcripts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Summarize all transcripts
  python scripts/generate_summaries.py
  
  # Summarize first 5 transcripts
  python scripts/generate_summaries.py --limit 5
  
  # Summarize single transcript
  python scripts/generate_summaries.py --transcript data/transcripts/lecture_01_transcript.json
  
  # Specify custom output directory
  python scripts/generate_summaries.py --output data/my_summaries
        """,
    )
    
    parser.add_argument(
        "--transcript-dir",
        type=Path,
        default=project_root / "data" / "transcripts",
        help="Directory containing transcript files (default: data/transcripts)",
    )
    
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=project_root / "data" / "summaries",
        help="Output directory for summaries (default: data/summaries)",
    )
    
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        help="Limit number of transcripts to process",
    )
    
    parser.add_argument(
        "--transcript",
        "-t",
        type=Path,
        help="Process single transcript file",
    )
    
    args = parser.parse_args()
    
    # Validate inputs
    if args.transcript:
        if not args.transcript.exists():
            logger.error(f"Transcript file not found: {args.transcript}")
            sys.exit(1)
    else:
        if not args.transcript_dir.exists():
            logger.error(f"Transcript directory not found: {args.transcript_dir}")
            logger.info("\n📝 TIP: Run Phase 2 ASR pipeline first to generate transcripts:")
            logger.info("   python scripts/run_phase2_asr.py")
            sys.exit(1)
        
        # Check if directory has transcripts
        transcript_files = list(args.transcript_dir.glob("*.json"))
        if not transcript_files:
            logger.error(f"No transcript files found in {args.transcript_dir}")
            sys.exit(1)
        
        logger.info(f"Found {len(transcript_files)} transcript files")
    
    # Load config
    config = load_config()
    
    # Generate summaries
    generate_summaries(
        transcript_dir=args.transcript_dir,
        output_dir=args.output,
        config=config,
        limit=args.limit,
        single_transcript=args.transcript,
    )


if __name__ == "__main__":
    main()
