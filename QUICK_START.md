# 🚀 Quick Start Guide — Interactive Lecture Intelligence

## 📊 Computational Requirements

### Phase-by-Phase Breakdown

| Phase | Computation | Time (CPU) | Time (GPU) | Memory |
|-------|-------------|------------|------------|--------|
| Phase 1: Data Ingestion | Light | 1-5 min | N/A | 2 GB |
| **Phase 2: ASR (Whisper)** | **HEAVY** | **2-8 hrs** | **10-30 min** | **8-16 GB** |
| Phase 3: Embedding | Moderate | 10-30 min | 2-5 min | 4-8 GB |
| Phase 4-5: RAG Setup | Light | 5-10 min | 1-2 min | 4 GB |
| Phase 6: Knowledge Graph | Light | 2-5 min | N/A | 2 GB |
| Phase 7: Flashcards | Light | 3-8 min | N/A | 2 GB |
| Phase 8: Summarization | Light | 5-15 min | N/A | 2 GB |

### 🔥 Critical: Phase 2 (ASR) is the Bottleneck

**Whisper large-v3 model:**
- Model size: ~3 GB download
- **CPU processing**: 50-100x slower than real-time (1 hour audio = 2-4 hours processing)
- **GPU processing**: 2-5x real-time (1 hour audio = 10-20 minutes)
- **Recommended**: Use GPU or cloud compute (Google Colab, Lambda Labs, RunPod)

### 💡 Recommendation

**Local (CPU only):**
- Use for testing with 1-2 short lectures (<10 min each)
- Or use smaller Whisper model: `base` or `small`
- Total time: 30-60 minutes

**Online Compute (GPU recommended):**
- ✅ **Best choice for production** with multiple lectures
- Providers: Google Colab (free T4 GPU), Lambda Labs, RunPod, Vast.ai
- Total time: 20-45 minutes for full pipeline

---

## 🎯 Running the Complete Pipeline

### Prerequisites

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Download spaCy models
python -m spacy download en_core_web_sm
python -m spacy download en_core_web_trf

# 3. Configure LLM (choose one)
# Option A: Local LLM with Ollama
ollama pull llama3

# Option B: Cloud LLM with Groq (get API key from console.groq.com)
export GROQ_API_KEY="your-api-key-here"
```

### Configuration

Edit `config/config.yaml`:

```yaml
# For CPU-only (testing)
asr_model_size: "base"        # or "small" (faster, less accurate)
device: "cpu"

# For GPU (production)
asr_model_size: "large-v3"    # best accuracy
device: "cuda"

# LLM choice
llm:
  provider: "ollama"            # or "groq" for cloud API
  model: "llama3"               # or "llama3-8b-8192" for Groq
```

---

## 📝 Step-by-Step Execution

### Phase 1: Prepare Audio Data

```bash
# Place your lecture audio files in data/raw_audio/
# Supported formats: .wav, .mp3, .flac, .ogg, .m4a

# Example structure:
data/raw_audio/
  ├── lecture_01.mp3
  ├── lecture_02.wav
  └── lecture_03.mp3

# Run audio normalization (optional but recommended)
python scripts/run_phase1_pipeline.py
```

**Expected output:** Normalized audio in `data/processed_audio/`

---

### Phase 2: Speech-to-Text (ASR) 🔥 HEAVY

```bash
# Process all audio files
python scripts/run_phase2_asr.py

# Or process specific file
python scripts/run_phase2_asr.py --audio data/raw_audio/lecture_01.mp3

# For faster testing (less accurate)
python scripts/run_phase2_asr.py --model-size base
```

**Expected output:** 
- Transcripts in `data/transcripts/` (JSON files)
- Segments in `data/segments/`
- Logs in `logs/asr_pipeline.log`

**Time estimate:**
- CPU: 2-8 hours for 3-5 lectures
- GPU: 10-30 minutes for 3-5 lectures

**💡 Tip:** This is the slowest phase. Consider:
1. Testing with 1 short file first
2. Using smaller model (`base` or `small`)
3. Running on Google Colab with free GPU

---

### Phase 3: Embedding & Vector Database

```bash
# Generate embeddings and index transcripts
python scripts/run_phase3_indexing.py

# Verify indexing worked
python scripts/test_retrieval.py
```

**Expected output:**
- Chunks in `data/chunks/`
- Vector database in `vector_db/`
- Collection: `lecture_index`

**Time:** 2-10 minutes (GPU helps but not critical)

---

### Phase 4-5: Test RAG System

```bash
# Test question answering
python scripts/test_rag_system.py

# Example queries:
# - "What is gradient descent?"
# - "Explain backpropagation"
# - "What is the KMP algorithm?"
```

**Expected output:** Answers with source citations and timestamps

**Time:** 1-2 minutes per query

---

### Phase 6: Generate Knowledge Graph

```bash
# Build concept graph from all transcripts
python scripts/build_concept_graph.py

# Limit to specific lectures
python scripts/build_concept_graph.py --limit 3

# View interactive graph
open frontend/concept_graph.html
```

**Expected output:**
- Graph data in `data/knowledge_graph/`
- Interactive HTML visualization
- JSON export of concepts and relationships

**Time:** 2-5 minutes

---

### Phase 7: Generate Flashcards

```bash
# Generate flashcards from all transcripts
python scripts/generate_flashcards.py

# Single transcript
python scripts/generate_flashcards.py --transcript data/transcripts/lecture_01_transcript.json

# Export formats: JSON, CSV, Anki
python scripts/generate_flashcards.py --formats json csv anki
```

**Expected output:**
- Flashcards in `data/flashcards/`
- Per-lecture files: `lecture_01_flashcards.json`
- Combined file: `all_flashcards.json`

**Time:** 3-8 minutes (depends on LLM speed)

---

### Phase 8: Generate Summaries

```bash
# Summarize all lectures
python scripts/generate_summaries.py

# Single lecture
python scripts/generate_summaries.py --transcript data/transcripts/lecture_01_transcript.json

# Limit batch size
python scripts/generate_summaries.py --limit 5
```

**Expected output:**
- Summaries in `data/summaries/`
- Each file: summary, key concepts, definitions
- Format: `lecture_01_summary.json`

**Time:** 5-15 minutes (depends on LLM speed)

---

## 🖥️ Start the Application

### 1. Start Backend API

```bash
# Terminal 1: Start FastAPI backend
cd /Users/rishiwalia/Documents/Documents/speech_rag
uvicorn backend.app.main:app --reload --port 8000

# Check health
curl http://localhost:8000/health
```

### 2. Start Frontend UI

```bash
# Terminal 2: Start Streamlit frontend
streamlit run frontend/streamlit_app.py

# Opens automatically at http://localhost:8501
```

### 3. Use the Application

**Features:**
- 💬 **Text Query**: Ask questions about lectures
- 🎤 **Audio Query**: Speak your question
- 📝 **Lecture Summary**: View summaries, key concepts, definitions
- 🎴 **Study Flashcards**: Interactive flashcard study mode
- 🧠 **Knowledge Graph**: Explore concept relationships
- 📜 **History**: View past queries

---

## ⚡ Quick Test (5 Minutes)

For immediate testing without running full pipeline:

```bash
# 1. Create sample transcripts
python scripts/create_sample_transcripts.py

# 2. Index samples
python scripts/run_phase3_indexing.py

# 3. Generate flashcards
python scripts/generate_flashcards.py --limit 1

# 4. Generate summaries
python scripts/generate_summaries.py --limit 1

# 5. Start app
streamlit run frontend/streamlit_app.py
```

---

## 🌐 Running on Cloud/Colab

### Google Colab Setup

```python
# 1. Clone repository
!git clone https://github.com/your-repo/speech_rag.git
%cd speech_rag

# 2. Install dependencies
!pip install -r requirements.txt
!python -m spacy download en_core_web_sm
!python -m spacy download en_core_web_trf

# 3. Check GPU
!nvidia-smi

# 4. Upload audio files to data/raw_audio/
from google.colab import files
# Upload via UI or mount Google Drive

# 5. Run Phase 2 with GPU
!python scripts/run_phase2_asr.py

# 6. Download results
from google.colab import files
!zip -r transcripts.zip data/transcripts/
files.download('transcripts.zip')
```

### Lambda Labs / RunPod

```bash
# SSH into instance
ssh user@instance-ip

# Clone and setup
git clone https://github.com/your-repo/speech_rag.git
cd speech_rag
pip install -r requirements.txt

# Verify GPU
nvidia-smi

# Run pipeline
python scripts/run_phase2_asr.py
python scripts/run_phase3_indexing.py
python scripts/generate_flashcards.py
python scripts/generate_summaries.py

# Download results via scp
scp -r user@instance-ip:/path/to/data/transcripts ./data/
scp -r user@instance-ip:/path/to/data/flashcards ./data/
scp -r user@instance-ip:/path/to/data/summaries ./data/
```

---

## 🔧 Troubleshooting

### Out of Memory

```yaml
# Reduce batch sizes in config.yaml
embedding_batch_size: 16    # default: 32
batch_size: 2               # default: 4
```

### Slow ASR

```yaml
# Use smaller model
asr_model_size: "base"      # or "small"
```

### LLM Errors

```bash
# Test Ollama
ollama list
ollama run llama3 "test"

# Or switch to Groq API
# Edit config.yaml:
llm:
  provider: "groq"
  model: "llama3-8b-8192"

# Set API key
export GROQ_API_KEY="your-key"
```

---

## 📈 Performance Tips

1. **Phase 2 (ASR)**: Use GPU or reduce model size
2. **Phase 3 (Embedding)**: GPU speeds up 3-5x
3. **Phases 7-8 (LLM)**: Use Groq API for faster responses
4. **Batch processing**: Use `--limit` flag for testing
5. **Incremental**: Process lectures one at a time if memory limited

---

## 📊 Expected Results

After running full pipeline:

```
data/
├── transcripts/        # 3-5 JSON files
├── chunks/             # 50-200 chunk files
├── flashcards/         # JSON/CSV/Anki files
├── summaries/          # JSON summary files
└── knowledge_graph/    # Graph JSON + HTML viz

vector_db/              # ChromaDB collection
logs/                   # Pipeline logs
```

**Total disk space:** 500 MB - 2 GB (depends on audio length)

---

## 🎓 Recommended Workflow

### For Testing (30 min total)
1. Use 1-2 short audio files (5-10 min each)
2. Use `base` Whisper model
3. Run on local machine
4. Test all features

### For Production (45 min total on GPU)
1. Upload all lecture audio
2. Use `large-v3` Whisper model
3. Run Phase 2 on Google Colab (free T4 GPU)
4. Download transcripts
5. Run Phases 3-8 locally (light computation)
6. Deploy application

---

## 🚀 Next Steps

After running the pipeline:

1. **Customize**: Edit prompts in `src/llm/rag_prompt.py`
2. **Evaluate**: Check `logs/rag_metrics.csv` for performance
3. **Extend**: Add new features to education modules
4. **Deploy**: Use Docker or cloud hosting
5. **Share**: Export flashcards/summaries for students

---

## 📞 Support

- Check logs in `logs/` directory
- Run tests: `pytest tests/ -v`
- Review README.md for detailed documentation
- Check KNOWLEDGE_GRAPH_GUIDE.md, FLASHCARD_GUIDE.md
