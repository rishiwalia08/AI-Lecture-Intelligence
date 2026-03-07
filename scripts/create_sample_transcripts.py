#!/usr/bin/env python3
"""
create_sample_transcripts.py
=============================
Generate sample lecture transcripts for testing the knowledge graph pipeline.

Usage:
    python scripts/create_sample_transcripts.py [--output-dir DIR] [--num-files N]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Sample lecture content on various CS topics
SAMPLE_LECTURES = [
    {
        "lecture_id": "ml_fundamentals",
        "topic": "Machine Learning Fundamentals",
        "content": """
        Machine learning is a subset of artificial intelligence that enables computers 
        to learn from data without explicit programming. Supervised learning uses labeled 
        training data to make predictions. Neural networks are inspired by biological 
        neurons and consist of interconnected layers. Deep learning uses multiple layers 
        to learn hierarchical representations. Backpropagation is the algorithm used to 
        train neural networks by computing gradients. Gradient descent optimizes the 
        loss function by iteratively updating weights. Overfitting occurs when a model 
        learns training data too well and fails to generalize. Regularization techniques 
        like dropout and L2 penalty prevent overfitting.
        """
    },
    {
        "lecture_id": "algorithms_intro",
        "topic": "Algorithm Analysis",
        "content": """
        Algorithm analysis involves studying computational complexity and efficiency. 
        Time complexity measures how runtime grows with input size. Space complexity 
        measures memory requirements. Big O notation describes asymptotic upper bounds. 
        Sorting algorithms like quicksort and mergesort have different performance 
        characteristics. Binary search is an efficient search algorithm for sorted arrays. 
        Dynamic programming solves problems by breaking them into overlapping subproblems. 
        Greedy algorithms make locally optimal choices. Graph algorithms like Dijkstra 
        find shortest paths. Hash tables provide constant-time average lookup.
        """
    },
    {
        "lecture_id": "neural_networks",
        "topic": "Deep Neural Networks",
        "content": """
        Deep neural networks contain multiple hidden layers between input and output. 
        Convolutional neural networks excel at computer vision tasks. Pooling layers 
        reduce spatial dimensions. Recurrent neural networks process sequential data. 
        Long short-term memory networks solve the vanishing gradient problem. Attention 
        mechanisms allow models to focus on relevant parts of input. Transformers use 
        self-attention for parallel processing. Batch normalization stabilizes training. 
        Activation functions like ReLU introduce non-linearity. Adam optimizer adapts 
        learning rates for each parameter.
        """
    },
    {
        "lecture_id": "data_structures",
        "topic": "Advanced Data Structures",
        "content": """
        Data structures organize and store data efficiently. Arrays provide constant-time 
        random access. Linked lists allow efficient insertion and deletion. Stacks follow 
        last-in-first-out order. Queues follow first-in-first-out order. Trees have 
        hierarchical structure with parent-child relationships. Binary search trees 
        maintain sorted order. Balanced trees like AVL trees guarantee logarithmic height. 
        Heaps support efficient priority queue operations. Graphs represent relationships 
        between entities. Tries efficiently store and search strings.
        """
    },
    {
        "lecture_id": "computer_vision",
        "topic": "Computer Vision",
        "content": """
        Computer vision enables machines to interpret visual information. Image 
        preprocessing includes normalization and augmentation. Feature extraction 
        identifies relevant patterns. Edge detection finds boundaries in images. 
        Object detection locates objects with bounding boxes. Image segmentation 
        classifies each pixel. Convolutional neural networks automatically learn 
        features. Transfer learning reuses pretrained models. Residual connections 
        enable very deep networks. Generative adversarial networks create realistic 
        images.
        """
    },
    {
        "lecture_id": "nlp_basics",
        "topic": "Natural Language Processing",
        "content": """
        Natural language processing analyzes human language computationally. 
        Tokenization splits text into words or subwords. Word embeddings represent 
        words as dense vectors. Recurrent neural networks model sequential dependencies. 
        Attention mechanisms weigh importance of different words. Transformers 
        revolutionized NLP with parallel processing. BERT uses bidirectional context. 
        Language models predict next words. Named entity recognition identifies 
        entities. Sentiment analysis determines emotional tone. Machine translation 
        converts between languages.
        """
    },
]


def create_transcript(lecture_data: dict, duration: float = 60.0) -> dict:
    """
    Create a transcript JSON from lecture data.
    
    Args:
        lecture_data: Dictionary with lecture_id, topic, and content
        duration: Total lecture duration in seconds
        
    Returns:
        Transcript dictionary
    """
    content = lecture_data["content"].strip()
    sentences = [s.strip() for s in content.split('.') if s.strip()]
    
    # Create segments from sentences
    segments = []
    segment_duration = duration / len(sentences)
    
    for i, sentence in enumerate(sentences):
        start_time = i * segment_duration
        end_time = start_time + segment_duration
        
        segments.append({
            "segment_id": f"{i+1:03d}",
            "text": sentence + ".",
            "start": round(start_time, 2),
            "end": round(end_time, 2),
        })
    
    return {
        "lecture_id": lecture_data["lecture_id"],
        "topic": lecture_data["topic"],
        "num_segments": len(segments),
        "total_duration": duration,
        "segments": segments,
        "text": content,
    }


def main():
    """Generate sample transcripts."""
    parser = argparse.ArgumentParser(
        description="Generate sample lecture transcripts for testing"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/transcripts"),
        help="Output directory for transcripts",
    )
    parser.add_argument(
        "--num-files",
        type=int,
        help="Number of files to generate (default: all)",
    )
    
    args = parser.parse_args()
    
    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine which lectures to generate
    lectures = SAMPLE_LECTURES
    if args.num_files:
        lectures = lectures[:args.num_files]
    
    print(f"Generating {len(lectures)} sample transcripts...")
    print(f"Output directory: {args.output_dir}")
    print()
    
    # Generate transcripts
    for lecture_data in lectures:
        transcript = create_transcript(lecture_data)
        
        # Save to file
        output_path = args.output_dir / f"{lecture_data['lecture_id']}_transcript.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(transcript, f, indent=2)
        
        print(f"✅ Created: {output_path.name}")
        print(f"   Topic: {lecture_data['topic']}")
        print(f"   Segments: {transcript['num_segments']}")
        print()
    
    print("=" * 60)
    print("✅ Done! Sample transcripts generated.")
    print()
    print("Next steps:")
    print("  1. Run knowledge graph pipeline:")
    print("     python scripts/build_concept_graph.py")
    print()
    print("  2. Or use quick start:")
    print("     ./quick_start_kg.sh")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
