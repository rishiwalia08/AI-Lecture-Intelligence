#!/bin/bash
# 🚀 Complete Local Setup Script
# Run this after downloading transcripts from Colab

set -e

echo "=========================================="
echo "🎓 Speech RAG - Post-Colab Setup"
echo "=========================================="

# Check if transcripts exist
if [ ! -d "data/transcripts" ] || [ -z "$(ls -A data/transcripts 2>/dev/null)" ]; then
    echo "❌ No transcripts found in data/transcripts/"
    echo ""
    echo "Did you download transcripts_output.zip from Colab?"
    echo "If yes, extract it first:"
    echo "  unzip transcripts_output.zip"
    exit 1
fi

echo "✅ Found transcripts"
ls -lh data/transcripts/ | grep -E "\.json$" | wc -l | xargs echo "   Files:"

# Install dependencies if needed
echo ""
echo "📦 Checking dependencies..."
pip install -q -r requirements.txt

# Download spaCy models
echo ""
echo "📥 Downloading spaCy models..."
python -m spacy download en_core_web_sm 2>/dev/null || echo "   (already installed)"
python -m spacy download en_core_web_trf 2>/dev/null || echo "   (already installed)"

# Check LLM setup
echo ""
echo "🤖 Checking LLM setup..."
if command -v ollama &> /dev/null; then
    echo "✅ Ollama found"
    ollama list | grep -q "llama3" && echo "   ✅ llama3 model ready" || echo "   ⚠️  Run: ollama pull llama3"
else
    echo "⚠️  Ollama not found. Install from https://ollama.com"
    echo "   Or use Groq API: export GROQ_API_KEY='your-key'"
fi

# Phase 3: Embedding & Indexing
echo ""
echo "=========================================="
echo "📊 Phase 3: Embedding & Vector Database"
echo "=========================================="
python scripts/run_phase3_indexing.py

# Phase 6: Knowledge Graph
echo ""
echo "=========================================="
echo "🧠 Phase 6: Knowledge Graph"
echo "=========================================="
python scripts/build_concept_graph.py

# Phase 7: Flashcards
echo ""
echo "=========================================="
echo "🎴 Phase 7: Flashcard Generation"
echo "=========================================="
python scripts/generate_flashcards.py

# Phase 8: Summaries
echo ""
echo "=========================================="
echo "📝 Phase 8: Lecture Summarization"
echo "=========================================="
python scripts/generate_summaries.py

echo ""
echo "=========================================="
echo "✅ SETUP COMPLETE!"
echo "=========================================="
echo ""
echo "🚀 Start the application:"
echo ""
echo "   Terminal 1: uvicorn backend.app.main:app --reload"
echo "   Terminal 2: streamlit run frontend/streamlit_app.py"
echo ""
echo "📊 Generated files:"
echo "   - Embeddings: vector_db/"
echo "   - Knowledge Graph: data/knowledge_graph/"
echo "   - Flashcards: data/flashcards/"
echo "   - Summaries: data/summaries/"
