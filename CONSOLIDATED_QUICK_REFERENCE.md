# Speech RAG - Consolidated Quick Reference Guide

> **Comprehensive reference for all 8 phases of the Speech RAG system.** This document consolidates all quick reference, guides, and shell scripts. Use this for quick lookups; see README.md for detailed architecture.

---

## Table of Contents

1. [Phase 1: Data Preparation](#phase-1-data-preparation)
2. [Phase 2: Speech Recognition (Whisper)](#phase-2-speech-recognition-whisper)
3. [Phase 3: Vector Indexing](#phase-3-vector-indexing)
4. [Phase 4: Hybrid Retrieval](#phase-4-hybrid-retrieval)
5. [Phase 5: RAG Answer Generation](#phase-5-rag-answer-generation)
6. [Phase 6: Knowledge Graph](#phase-6-knowledge-graph)
7. [Phase 7: Flashcards](#phase-7-flashcards)
8. [Phase 8: Lecture Summarization](#phase-8-lecture-summarization)
9. [Hugging Face Migration & Cloud Deployment](#hugging-face-migration--cloud-deployment)

---

# Phase 1: Data Preparation

## Quick Start

```bash
python scripts/run_phase1_pipeline.py
```

## What It Does

- Loads dataset metadata
- Normalizes audio to **16 kHz mono WAV**
- Validates dataset structure
- Prepares data for transcription

## Key Files

- `scripts/run_phase1_pipeline.py` — Pipeline orchestration
- `src/data_ingestion/load_datasets.py` — Dataset loading
- `src/audio_processing/audio_normalizer.py` — Audio preprocessing

## Configuration

Edit `config/config.yaml`:

```yaml
data_ingestion:
  datasets:
    - commonvoice_indian
    - librispeech
    - tedlium
  sample_rate: 16000
  mono: true
```

---

# Phase 2: Speech Recognition (Whisper)

## Quick Start

```bash
python scripts/run_phase2_asr.py
```

## What It Does

- Transcribes audio using OpenAI Whisper
- Produces timestamped segments
- Saves transcripts as JSON with timestamps

## Key Commands

```bash
# Basic transcription
python scripts/run_phase2_asr.py

# With custom config
python scripts/run_phase2_asr.py --config config/config.yaml

# Specific audio files
python scripts/run_phase2_asr.py --audio-dir data/raw_audio
```

## Key Files

- `scripts/run_phase2_asr.py` — ASR pipeline
- `src/asr/whisper_transcriber.py` — Whisper integration
- `src/asr/timestamp_formatter.py` — Timestamp handling

## Output Format

```json
{
  "lecture_id": "ml_basics_01",
  "duration": 3600,
  "segments": [
    {
      "id": 1,
      "start": 0.0,
      "end": 15.5,
      "text": "Today we'll discuss gradient descent..."
    }
  ]
}
```

## Configuration

```yaml
asr:
  model: "base"  # tiny, base, small, medium, large
  device: "cuda"  # or "cpu"
  language: "en"
  sample_rate: 16000
```

---

# Phase 3: Vector Indexing

## Quick Start

```bash
python scripts/run_phase3_indexing.py
```

## What It Does

- Chunks transcripts into semantic segments
- Generates embeddings (BGE-M3)
- Stores vectors in ChromaDB
- Creates metadata index

## Key Commands

```bash
# Basic indexing
python scripts/run_phase3_indexing.py

# Rebuild vector database
python scripts/run_phase3_indexing.py --rebuild

# Custom chunk size
python scripts/run_phase3_indexing.py --chunk-size 500
```

## Key Files

- `scripts/run_phase3_indexing.py` — Indexing pipeline
- `src/embedding/chunking.py` — Text chunking strategies
- `src/embedding/embedder.py` — BGE-M3 embeddings
- `src/vectorstore/chroma_manager.py` — Vector storage

## Configuration

```yaml
embedding:
  model: "BAAI/bge-m3"
  chunk_size: 300
  chunk_overlap: 50
  
vectorstore:
  type: "chroma"
  persist_directory: "vector_db"
```

## Database Location

```
vector_db/
  ├── data/
  └── metadata.db
```

---

# Phase 4: Hybrid Retrieval

## Quick Start

```bash
from src.retrieval.hybrid_search import HybridSearch

retriever = HybridSearch()
results = retriever.search("What is gradient descent?", k=5)
```

## What It Does

- Combines semantic (vector) search with keyword (BM25) search
- Reranks results using BGE reranker
- Returns top-k most relevant segments

## Key Features

- **Semantic Search**: Dense vector similarity
- **Keyword Search**: BM25 sparse retrieval
- **Reranking**: BGE-Large reranker for quality
- **Metadata Filtering**: Filter by lecture, date, etc.

## Key Files

- `src/retrieval/hybrid_search.py` — Hybrid retrieval
- `src/retrieval/query_processor.py` — Query processing
- `src/retrieval/reranker.py` — Result reranking
- `src/retrieval/metadata_builder.py` — Metadata management

## Configuration

```yaml
retrieval:
  bm25_weight: 0.3  # vs semantic (0.7)
  reranker_model: "BAAI/bge-reranker-large"
  top_k: 10
  score_threshold: 0.5
```

---

# Phase 5: RAG Answer Generation

## Quick Start

```bash
# Start backend
uvicorn backend.app.main:app --reload

# Query via API
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is gradient descent?"}'
```

## What It Does

- Retrieves relevant lecture segments
- Augments LLM with retrieved context
- Generates grounded answers with citations
- Returns exact lecture timestamps

## Key API Endpoints

```
POST   /query                    → Search and answer
GET    /lectures                 → List available lectures
POST   /chat                     → Multi-turn conversation
```

## Response Example

```json
{
  "answer": "Gradient descent is an optimization algorithm...",
  "sources": [
    {
      "lecture": "ML Basics 01",
      "timestamp": "14:02",
      "segment": "Neural networks use backpropagation..."
    }
  ],
  "confidence": 0.92
}
```

## Key Files

- `backend/app/main.py` — FastAPI server
- `backend/app/routes.py` — API endpoints
- `src/llm/llm_loader.py` — LLM initialization
- `src/llm/answer_generator.py` — Answer generation
- `src/llm/rag_prompt.py` — Prompt templates

## LLM Providers

```yaml
llm:
  provider: "huggingface"  # huggingface, groq, ollama
  model: "mistralai/Mistral-7B-Instruct"
  temperature: 0.2
  max_tokens: 500
```

---

# Phase 6: Knowledge Graph

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install spacy networkx pyvis
   python -m spacy download en_core_web_trf
   ```

2. **Generate graph:**
   ```bash
   python scripts/build_concept_graph.py
   ```

3. **View visualization:**
   ```bash
   open frontend/concept_graph.html
   # OR
   streamlit run frontend/streamlit_app.py
   ```

## Key Commands

```bash
# One-liner setup
./quick_start_kg.sh

# With options
python scripts/build_concept_graph.py --limit 10 --max-viz-nodes 200

# Generate sample data
python scripts/create_sample_transcripts.py

# Run tests
pytest tests/test_concept_extractor.py tests/test_graph_builder.py -v
```

## Key Files

**Source Code:**
- `src/knowledge_graph/concept_extractor.py` — Concept extraction
- `src/knowledge_graph/graph_builder.py` — Graph construction
- `scripts/build_concept_graph.py` — Pipeline script

**Outputs:**
- `data/knowledge_graph/concept_graph.json` — Graph data
- `frontend/concept_graph.html` — Visualization

## Programmatic Usage

```python
from src.knowledge_graph.concept_extractor import ConceptExtractor
from src.knowledge_graph.graph_builder import GraphBuilder

# Extract concepts
extractor = ConceptExtractor()
concepts = extractor.extract_concepts("Text here")

# Build graph
builder = GraphBuilder()
builder.build_from_transcripts(Path("data/transcripts"), extractor)
builder.visualize(Path("frontend/concept_graph.html"))
```

## API Endpoints

```
GET  /knowledge_graph        → Get graph JSON data
```

## Configuration

```yaml
knowledge_graph:
  spacy_model: "en_core_web_trf"     # Transformer model
  min_frequency: 2                    # Prune threshold
  max_viz_nodes: 100                  # Visualization limit
```

## Visualization Tips

- **Hover over nodes** → See details
- **Click & drag** → Rearrange layout
- **Mouse wheel** → Zoom in/out
- **Navigation controls** → Bottom right

**Node Colors:**
- 🔴 **Red** → Highly connected (>5 edges)
- 🟢 **Teal** → Moderately connected (>2 edges)
- ⚪ **Gray** → Sparsely connected

## Typical Workflow

1. Run Phase 2 (if needed): `python scripts/run_phase2_asr.py`
2. Build knowledge graph: `python scripts/build_concept_graph.py`
3. View in Streamlit: `streamlit run frontend/streamlit_app.py`
4. Or open directly: `open frontend/concept_graph.html`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Model not found" | `python -m spacy download en_core_web_trf` |
| "No transcripts found" | `python scripts/create_sample_transcripts.py` OR `python scripts/run_phase2_asr.py` |
| "Graph not generated" in UI | `python scripts/build_concept_graph.py` |
| Too many/few concepts | Adjust `--min-frequency` and `--max-viz-nodes` |

## Performance

- **Processing:** ~1-5 seconds/transcript
- **Model load:** ~5-10 seconds (one-time)
- **Memory:** ~1-2GB (transformer model)
- **Scales to:** 100+ transcripts efficiently

---

# Phase 7: Flashcards

---

# Phase 6: Knowledge Graph

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install spacy networkx pyvis
   python -m spacy download en_core_web_trf
   ```

2. **Generate graph:**
   ```bash
   python scripts/build_concept_graph.py
   ```

3. **View visualization:**
   ```bash
   open frontend/concept_graph.html
   # OR
   streamlit run frontend/streamlit_app.py
   ```

## Key Commands

```bash
# One-liner setup
./quick_start_kg.sh

# With options
python scripts/build_concept_graph.py --limit 10 --max-viz-nodes 200

# Generate sample data
python scripts/create_sample_transcripts.py

# Run tests
pytest tests/test_concept_extractor.py tests/test_graph_builder.py -v
```

## Key Files

**Source Code:**
- `src/knowledge_graph/concept_extractor.py` — Concept extraction
- `src/knowledge_graph/graph_builder.py` — Graph construction
- `scripts/build_concept_graph.py` — Pipeline script

**Outputs:**
- `data/knowledge_graph/concept_graph.json` — Graph data
- `frontend/concept_graph.html` — Visualization

**Documentation:**
- `KNOWLEDGE_GRAPH_GUIDE.md` — Full guide
- `PHASE6_SUMMARY.md` — Implementation summary

## Programmatic Usage

```python
from src.knowledge_graph.concept_extractor import ConceptExtractor
from src.knowledge_graph.graph_builder import GraphBuilder

# Extract concepts
extractor = ConceptExtractor()
concepts = extractor.extract_concepts("Text here")

# Build graph
builder = GraphBuilder()
builder.build_from_transcripts(Path("data/transcripts"), extractor)
builder.visualize(Path("frontend/concept_graph.html"))
```

## API Endpoints

```
GET  /knowledge_graph        → Get graph JSON data
```

**Example:**
```bash
curl http://localhost:8000/knowledge_graph
```

## Configuration

Edit `config/config.yaml`:

```yaml
knowledge_graph:
  spacy_model: "en_core_web_trf"     # Transformer model
  min_frequency: 2                    # Prune threshold
  max_viz_nodes: 100                  # Visualization limit
```

## Visualization Tips

- **Hover over nodes** → See details
- **Click & drag** → Rearrange layout
- **Mouse wheel** → Zoom in/out
- **Navigation controls** → Bottom right

**Node Colors:**
- 🔴 **Red** → Highly connected (>5 edges)
- 🟢 **Teal** → Moderately connected (>2 edges)
- ⚪ **Gray** → Sparsely connected

## Typical Knowledge Graph Workflow

1. Run Phase 2 (if needed):
   ```bash
   python scripts/run_phase2_asr.py
   ```

2. Build knowledge graph:
   ```bash
   python scripts/build_concept_graph.py
   ```

3. View in Streamlit:
   ```bash
   streamlit run frontend/streamlit_app.py
   ```
   → Click "🔍 Explore Concept Graph"

4. Or open directly:
   ```bash
   open frontend/concept_graph.html
   ```

## Knowledge Graph Troubleshooting

| Issue | Solution |
|-------|----------|
| "Model not found" | `python -m spacy download en_core_web_trf` |
| "No transcripts found" | `python scripts/create_sample_transcripts.py` OR `python scripts/run_phase2_asr.py` |
| "Graph not generated" in UI | `python scripts/build_concept_graph.py` |
| Too many/few concepts | Adjust `--min-frequency` and `--max-viz-nodes` |

## Knowledge Graph Performance

- **Processing:** ~1-5 seconds/transcript
- **Model load:** ~5-10 seconds (one-time)
- **Memory:** ~1-2GB (transformer model)
- **Scales to:** 100+ transcripts efficiently

---

# Phase 7: Flashcards

## Quick Start

1. **Generate flashcards:**
   ```bash
   python scripts/generate_flashcards.py
   ```

2. **Study in Streamlit:**
   ```bash
   streamlit run frontend/streamlit_app.py
   ```
   → Navigate to "🎴 Study Flashcards" tab

3. **Or import to Anki:**
   → File → Import → `data/flashcards/all_flashcards.txt`

## Key Commands

```bash
# Basic usage
python scripts/generate_flashcards.py

# With options
python scripts/generate_flashcards.py \
    --limit 5 \
    --max-cards 15 \
    --formats json csv anki

# Use Groq API (faster)
python scripts/generate_flashcards.py \
    --provider groq \
    --model llama3-8b-8192

# Local Ollama
python scripts/generate_flashcards.py \
    --provider ollama \
    --model llama3
```

## Key Files

**Source Code:**
- `src/education/flashcard_generator.py` — LLM-powered generation
- `scripts/generate_flashcards.py` — Pipeline script

**Outputs:**
- `data/flashcards/<lecture>_flashcards.*` — Per-lecture files
- `data/flashcards/all_flashcards.*` — Combined files

**Documentation:**
- `FLASHCARD_GUIDE.md` — Complete guide
- `PHASE7_SUMMARY.md` — Implementation summary

## Output Formats

### JSON (`data/flashcards/*.json`)
```json
[
  {
    "question": "What is gradient descent?",
    "answer": "An optimization algorithm...",
    "lecture_id": "ml_basics"
  }
]
```

### CSV (`data/flashcards/*.csv`)
```
question,answer,lecture_id,topic
"What is...","An algorithm...","ml_basics","ML"
```

### Anki (`data/flashcards/*.txt`)
```
Question text	Answer text
```

## Streamlit UI Features

- Select flashcard set (individual lecture or all)
- View question
- Click "Show Answer" to reveal
- Navigate: Previous / Next
- Shuffle: Randomize order
- Reset: Return to start
- Progress tracker

## Programmatic Usage

```python
from src.education.flashcard_generator import FlashcardGenerator

# Initialize
generator = FlashcardGenerator(
    model_config={"provider": "ollama", "model": "llama3"},
    max_cards_per_chunk=10,
)

# Generate
flashcards = generator.generate_flashcards(
    text="Neural networks use backpropagation.",
    lecture_id="nn_basics"
)

# Save
generator.save_flashcards(
    flashcards,
    Path("output.json"),
    format="json"
)
```

## Import to Anki

1. Generate Anki format:
   ```bash
   python scripts/generate_flashcards.py --formats anki
   ```

2. Open Anki desktop app

3. Import:
   - File → Import
   - Select: `data/flashcards/all_flashcards.txt`
   - Type: "Text separated by tabs"

4. Start studying!

## Configuration

Edit `config/config.yaml`:

```yaml
llm:
  provider: "ollama"      # or "groq"
  model: "llama3"
  temperature: 0.2

flashcards:
  max_cards_per_chunk: 10
  formats: ["json", "csv", "anki"]

flashcards_path: data/flashcards
```

## Command-Line Options

| Option | Description |
|--------|-------------|
| `--config PATH` | Config file path |
| `--transcripts-dir PATH` | Transcripts directory |
| `--output-dir PATH` | Output directory |
| `--limit N` | Process only N transcripts |
| `--max-cards N` | Max cards per transcript |
| `--formats [json csv anki]` | Export formats |
| `--provider {ollama\|groq}` | LLM provider |
| `--model NAME` | LLM model name |

## Example Workflows

### Workflow 1: Generate and study in Streamlit
```bash
python scripts/generate_flashcards.py
streamlit run frontend/streamlit_app.py
```

### Workflow 2: Generate and import to Anki
```bash
python scripts/generate_flashcards.py --formats anki
# Open Anki → Import → all_flashcards.txt
```

### Workflow 3: Generate for specific lectures
```bash
python scripts/generate_flashcards.py --limit 3 --max-cards 20
```

### Workflow 4: Use Groq for fast generation
```bash
export GROQ_API_KEY="your_key"
python scripts/generate_flashcards.py --provider groq
```

## Study Tips

1. Try to recall before showing answer
2. Use shuffle for varied practice
3. Review regularly (spaced repetition)
4. Import to Anki for automatic scheduling
5. Focus on concepts you find difficult

## Flashcard File Locations

**Inputs:**
- `data/transcripts/*.json` — Source transcripts

**Outputs:**
- `data/flashcards/lecture_*.*` — Per-lecture files
- `data/flashcards/all_*.*` — Combined files

**Formats:**
- `*.json` — Structured data
- `*.csv` — Spreadsheet format
- `*.txt` — Anki import format

## Flashcard Troubleshooting

| Issue | Solution |
|-------|----------|
| No flashcards generated | Check LLM is running (ollama) or API key set (groq). Check transcripts exist in `data/transcripts/` |
| Poor quality flashcards | Lower temperature (0.1-0.2). Try different model |
| LLM timeout | Process fewer transcripts (`--limit 3`). Use faster provider (groq) |
| "No flashcards available" in UI | Run: `python scripts/generate_flashcards.py` |

## Flashcard Performance

- **Generation:** ~2-5 seconds/transcript (Ollama)
- **Generation:** <1 second/transcript (Groq)
- **Export:** Instant
- **Scales:** 100+ transcripts efficiently

## Testing

```bash
# Run tests
pytest tests/test_flashcard_generator.py -v

# With coverage
pytest tests/test_flashcard_generator.py --cov=src/education
```

---

# Phase 8: Lecture Summarization

## Quick Start

```bash
python scripts/generate_summaries.py
```

## What It Does

- Generates concise summaries of lecture transcripts
- Creates study notes for revision
- Extracts key takeaways per lecture
- Produces summaries in multiple formats

## Key Commands

```bash
# Generate all summaries
python scripts/generate_summaries.py

# Limit transcripts
python scripts/generate_summaries.py --limit 5

# Custom output formats
python scripts/generate_summaries.py --formats markdown pdf

# Specific lecture
python scripts/generate_summaries.py --lecture ml_basics_01
```

## Key Files

- `src/education/summary_generator.py` — Summary generation
- `scripts/generate_summaries.py` — Pipeline script

## Output Formats

- **Markdown** — For note-taking apps
- **PDF** — For printing/archiving
- **JSON** — For structured data

## Configuration

```yaml
summarization:
  summary_length: "medium"  # short, medium, long
  include_timestamps: true
  focus_areas: ["key_concepts", "examples", "conclusions"]
```

## Example Workflow

```bash
# Generate summaries
python scripts/generate_summaries.py

# View in Streamlit
streamlit run frontend/streamlit_app.py
# → Navigate to "📝 Lecture Summaries"
```

---

# Hugging Face Migration & Cloud Deployment

## Setup

### 1. Get Hugging Face API Key

```bash
# Visit: https://huggingface.co/settings/tokens
# Create new token with "Read" access
export HF_API_KEY='hf_your_token_here'
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
pip install huggingface_hub
```

### 3. Validate HF Integration

```bash
python test_hf_migration.py
# Expected: 7/7 tests passed ✅
```

## Local Testing

```bash
# Test RAG system
python scripts/test_rag_system.py

# Generate flashcards
python scripts/generate_flashcards.py --limit 1

# Generate summaries
python scripts/generate_summaries.py --limit 1

# Start frontend
streamlit run frontend/streamlit_app.py
```

## LLM Provider Selection

### Hugging Face (Recommended)

```python
from src.llm.llm_loader import LLMConfig, load_llm

config = LLMConfig(provider='huggingface')
llm = load_llm(config)
```

Edit `config/config.yaml`:

```yaml
llm:
  provider: "huggingface"
  model: "mistralai/Mistral-7B-Instruct"
  temperature: 0.2
```

### Groq (Alternative - Faster)

```python
config = LLMConfig(provider='groq')
llm = load_llm(config)
```

### Ollama (Local - Deprecated)

```python
config = LLMConfig(provider='ollama')
llm = load_llm(config)
```

## Environment Variables

```bash
# Method 1: Export
export HF_API_KEY='hf_your_token_here'

# Method 2: .env file (never commit!)
echo "HF_API_KEY=hf_your_token_here" > .env

# Method 3: Cloud dashboard (Render/Railway/GCP)
# Set environment variable in service settings
```

## Cloud Deployment

### Render (Recommended - 5 min setup)

```bash
# Push code
git push origin main

# In Render dashboard:
# 1. Select GitHub repo
# 2. Set environment variable: HF_API_KEY=hf_...
# 3. Auto-deploys on push!
```

**Build Command:**
```
pip install -r requirements.txt
```

**Start Command:**
```
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

### Railway.app

```bash
railway login
railway variables set HF_API_KEY=hf_...
railway up
```

### Google Cloud Run

```bash
docker build -t speech-rag .
gcloud run deploy speech-rag --source . \
  --set-env-vars=HF_API_KEY=hf_...
```

## Test Deployment

```bash
# Check deployment status
curl https://your-app.onrender.com

# Test API endpoint
curl -X POST https://your-app.onrender.com/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is gradient descent?"}'
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Invalid API key" | Check `HF_API_KEY` is set correctly |
| "Rate limited" | Wait or upgrade Hugging Face account |
| "Model not found" | Check `config.yaml` model name |
| "ImportError: huggingface_hub" | `pip install huggingface_hub` |
| Deployment fails | Check logs in Render/Railway dashboard |

## Performance Optimization

```bash
# Use smaller model for faster response
model: "mistralai/Mistral-7B"  # vs 70B

# Cache embeddings
embedding:
  cache_embeddings: true
  cache_ttl: 3600

# Use GPU if available
asr:
  device: "cuda"  # vs "cpu"
```

---

# Complete Workflow Example

```bash
# 1. Setup
pip install -r requirements.txt
export HF_API_KEY='hf_your_token'

# 2. Prepare data
python scripts/run_phase1_pipeline.py

# 3. Transcribe audio
python scripts/run_phase2_asr.py

# 4. Index vectors
python scripts/run_phase3_indexing.py

# 5. Generate flashcards
python scripts/generate_flashcards.py

# 6. Generate summaries
python scripts/generate_summaries.py

# 7. Build knowledge graph
python scripts/build_concept_graph.py

# 8. Start backend
uvicorn backend.app.main:app --reload

# 9. Run frontend (in another terminal)
streamlit run frontend/streamlit_app.py

# 10. Deploy to cloud
git push origin main  # Render auto-deploys
```

---

## Quick Reference Summary

| Phase | Command | Output |
|-------|---------|--------|
| 1 | `python scripts/run_phase1_pipeline.py` | Normalized audio |
| 2 | `python scripts/run_phase2_asr.py` | Transcripts w/ timestamps |
| 3 | `python scripts/run_phase3_indexing.py` | Vector database |
| 4 | N/A (library) | Hybrid retrieval |
| 5 | `uvicorn backend.app.main:app --reload` | API server |
| 6 | `python scripts/build_concept_graph.py` | Knowledge graph |
| 7 | `python scripts/generate_flashcards.py` | Flashcards |
| 8 | `python scripts/generate_summaries.py` | Summaries |

---

**Last Updated:** March 28, 2026

For additional details, see [README.md](README.md)
