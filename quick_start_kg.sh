#!/bin/bash
# quick_start_kg.sh
# =================
# Quick start script for Knowledge Graph generation
#
# Usage:
#   chmod +x quick_start_kg.sh
#   ./quick_start_kg.sh

set -e  # Exit on error

echo "=========================================="
echo "Knowledge Graph Quick Start"
echo "=========================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.10+"
    exit 1
fi

echo "✅ Python found: $(python3 --version)"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pip install -q spacy networkx pyvis
echo "✅ Dependencies installed"
echo ""

# Download spaCy model
echo "📥 Downloading spaCy model (en_core_web_trf)..."
if python3 -m spacy validate | grep -q "en_core_web_trf"; then
    echo "✅ Model already installed"
else
    python3 -m spacy download en_core_web_trf
    echo "✅ Model downloaded"
fi
echo ""

# Check for transcripts
echo "🔍 Checking for transcripts..."
TRANSCRIPT_DIR="data/transcripts"
if [ ! -d "$TRANSCRIPT_DIR" ] || [ -z "$(ls -A $TRANSCRIPT_DIR/*.json 2>/dev/null)" ]; then
    echo "⚠️  No transcripts found in $TRANSCRIPT_DIR"
    echo "   Run Phase 2 first: python scripts/run_phase2_asr.py"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    TRANSCRIPT_COUNT=$(ls -1 $TRANSCRIPT_DIR/*.json 2>/dev/null | wc -l)
    echo "✅ Found $TRANSCRIPT_COUNT transcript files"
fi
echo ""

# Run pipeline
echo "🚀 Running knowledge graph pipeline..."
python3 scripts/build_concept_graph.py "$@"
echo ""

# Check output
if [ -f "frontend/concept_graph.html" ]; then
    echo "=========================================="
    echo "✅ SUCCESS!"
    echo "=========================================="
    echo ""
    echo "Outputs:"
    echo "  • Graph files: data/knowledge_graph/concept_graph.*"
    echo "  • Visualization: frontend/concept_graph.html"
    echo ""
    echo "Next steps:"
    echo "  1. Open visualization: open frontend/concept_graph.html"
    echo "  2. Or run Streamlit: streamlit run frontend/streamlit_app.py"
    echo ""
else
    echo "⚠️  Pipeline completed but visualization not found"
fi
