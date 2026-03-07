# Interactive Lecture Intelligence — Speech RAG System

A modular Python pipeline that prepares lecture audio, transcribes it with
Whisper, and produces timestamped JSON segments for downstream RAG retrieval.

---

## Project Structure

```
speech_rag/
├── config/
│   └── config.yaml                  # Central configuration (Phase 1 + 2)
├── data/
│   ├── raw_audio/                   # Original lecture recordings
│   ├── processed_audio/             # Normalised 16 kHz WAV files
│   ├── transcripts/                 # Full JSON transcripts  ← Phase 2
│   ├── segments/                    # Per-segment JSON files ← Phase 2
│   ├── pdfs/                        # Lecture slide PDFs
│   └── dataset_metadata.csv         # Auto-generated metadata index
├── datasets/
│   ├── tedlium/                     # TED-LIUM Release 3
│   ├── librispeech/                 # LibriSpeech corpus
│   └── commonvoice_indian/          # Mozilla Common Voice (Indian EN)
├── src/
│   ├── asr/
│   │   ├── whisper_transcriber.py   # Whisper model loader + transcription
│   │   └── timestamp_formatter.py   # Segment formatting, I/O, validation
│   ├── data_ingestion/
│   │   └── load_datasets.py         # Dataset loaders + orchestrator
│   ├── audio_processing/
│   │   └── audio_normalizer.py      # Resample → mono → WAV
│   ├── anonymization/
│   │   └── pii_cleaner.py           # spaCy NER-based PII removal
│   └── utils/
│       └── logger.py                # Centralised logging
├── scripts/
│   ├── run_phase1_pipeline.py       # Phase 1 entrypoint
│   └── run_phase2_asr.py            # Phase 2 entrypoint
├── tests/
│   ├── test_load_datasets.py
│   ├── test_audio_normalizer.py
│   ├── test_pii_cleaner.py
│   ├── test_whisper_transcriber.py
│   └── test_timestamp_formatter.py
├── logs/
│   ├── pipeline.log                 # Phase 1 log
│   ├── asr_pipeline.log             # Phase 2 log
│   └── asr_metrics.csv              # Per-file ASR metrics
├── requirements.txt
├── pytest.ini
└── README.md
```

---

## Quick Start

```bash
# 1. Install all dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 2. Copy datasets into their directories (see table below)
# 3. Run Phase 1 — data ingestion & normalisation
python scripts/run_phase1_pipeline.py

# 4. Run Phase 2 — Whisper ASR transcription
python scripts/run_phase2_asr.py
```

**Dataset directories:**

| Dataset | Directory |
|---|---|
| TED-LIUM Release 3 | `datasets/tedlium/` |
| LibriSpeech | `datasets/librispeech/` |
| Common Voice (Indian EN) | `datasets/commonvoice_indian/` |
| Local lecture recordings | `data/raw_audio/` |

---

## Phase 1 — Data Ingestion & Preprocessing

```bash
python scripts/run_phase1_pipeline.py [--skip-normalization] [--dry-run]
```

| Step | Description | Output |
|---|---|---|
| 1 | Load metadata from all datasets | `data/dataset_metadata.csv` |
| 2 | Normalise audio → 16 kHz mono WAV | `data/processed_audio/` |
| 3 | Validate processed audio format | Console + `logs/pipeline.log` |
| 4 | Save enriched metadata | `data/dataset_metadata.csv` |

---

## Phase 2 — Whisper ASR Transcription

```bash
python scripts/run_phase2_asr.py [--backend openai|faster] [--limit N] [--dry-run]
```

| Step | Description | Output |
|---|---|---|
| 1 | Load metadata CSV | — |
| 2 | Load Whisper model (once) | — |
| 3 | Transcribe each audio file | — |
| 4 | Validate segment ordering & text | `logs/asr_pipeline.log` |
| 5 | Save full transcript JSON | `data/transcripts/<id>_transcript.json` |
| 6 | Save per-segment JSON files | `data/segments/<id>/<id>_segment_NNN.json` |
| 7 | Record per-file metrics | `logs/asr_metrics.csv` |

**Full transcript format:**

```json
{
  "lecture_id": "lecture_01",
  "num_segments": 3,
  "total_duration": 14.5,
  "segments": [
    {"segment_id": "001", "text": "The KMP algorithm is used for pattern matching.", "start": 0.0,  "end": 6.2},
    {"segment_id": "002", "text": "It runs in linear time.",                           "start": 6.2,  "end": 9.8},
    {"segment_id": "003", "text": "The prefix function avoids redundant comparisons.", "start": 9.8,  "end": 14.5}
  ]
}
```

---

## Module Usage

### Whisper Transcription

```python
from src.asr.whisper_transcriber import WhisperConfig, load_whisper_model, transcribe_with_metrics

config = WhisperConfig(model_size="large-v3", device="cuda", backend="openai")
model  = load_whisper_model(config)
segs, metrics = transcribe_with_metrics("data/processed_audio/lecture.wav", model, config)
print(f"RTF: {metrics.realtime_factor:.2f}")  # <1.0 = faster than real-time
```

### Transcript Formatting & Storage

```python
from src.asr.timestamp_formatter import format_transcript, save_full_transcript, save_segments, validate_transcript

transcript = format_transcript("lecture_01", segs)
result     = validate_transcript(transcript)   # is_valid, issues list
save_full_transcript(transcript, "data/transcripts")
save_segments(transcript, "data/segments")
```

### PII Anonymisation

```python
from src.anonymization.pii_cleaner import PIICleaner
cleaner = PIICleaner()
print(cleaner.clean_text_pii("Yesterday Rahul asked a question."))
# → "Yesterday [PERSON] asked a question."
```

---

## Running Tests

```bash
# All tests — no GPU or model download required
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=src --cov-report=term-missing
```

---

## Configuration Reference

| Key | Default | Description |
|---|---|---|
| `audio_sample_rate` | `16000` | Target sample rate (Hz) |
| `asr_model_size` | `large-v3` | Whisper model variant |
| `asr_backend` | `openai` | `"openai"` or `"faster"` |
| `device` | `cuda` | `"cuda"` (auto-falls back to `"cpu"`) |
| `batch_size` | `4` | Batch size for faster-whisper |
| `spacy_model` | `en_core_web_sm` | spaCy NER model |

---

## Logs & Metrics

| File | Contents |
|---|---|
| `logs/pipeline.log` | Phase 1 pipeline events |
| `logs/asr_pipeline.log` | Phase 2 transcription events + errors |
| `logs/asr_metrics.csv` | `file_name`, `audio_duration`, `processing_time`, `num_segments`, `realtime_factor` |

---

## Roadmap

- **Phase 1** ✅ Data ingestion & preprocessing
- **Phase 2** ✅ Whisper ASR transcription with timestamps
- **Phase 3** ✅ Embedding generation & vector storage
- **Phase 4** ✅ RAG retrieval & speech query interface
- **Phase 5** ✅ LLM answer generation
- **Phase 6** ✅ Concept knowledge graph generation
- **Phase 7** ✅ Flashcard generation for study

---

## Phase 7 — Flashcard Generation

Generate study flashcards from lecture transcripts using LLM for active learning and recall practice.

```bash
python scripts/generate_flashcards.py [--limit N] [--formats json csv anki]
```

### Quick Start

```bash
# Generate flashcards from all transcripts
python scripts/generate_flashcards.py

# Limit to 5 lectures, export as JSON and Anki
python scripts/generate_flashcards.py --limit 5 --formats json anki

# Specify LLM provider
python scripts/generate_flashcards.py --provider groq --model llama3-8b-8192
```

### Pipeline Steps

| Step | Description | Output |
|---|---|---|
| 1 | Load transcript files | From `data/transcripts/` |
| 2 | Generate Q&A pairs using LLM | Question-answer flashcards |
| 3 | Save in multiple formats | JSON, CSV, Anki |

### Output Formats

**JSON Format:**
```json
[
  {
    "question": "What is gradient descent?",
    "answer": "An optimization algorithm used to minimize loss during training.",
    "lecture_id": "ml_fundamentals",
    "topic": "Machine Learning"
  }
]
```

**CSV Format:** Tab-delimited with headers (question, answer, lecture_id, topic)

**Anki Format:** Tab-separated plain text for direct import to Anki

### Outputs

| File | Description |
|---|---|
| `data/flashcards/<lecture_id>_flashcards.json` | Per-lecture flashcards (JSON) |
| `data/flashcards/<lecture_id>_flashcards.csv` | Per-lecture flashcards (CSV) |
| `data/flashcards/<lecture_id>_flashcards.txt` | Per-lecture flashcards (Anki) |
| `data/flashcards/all_flashcards.*` | Combined flashcards from all lectures |

### Frontend Integration

Study flashcards in the Streamlit UI:

1. Run: `streamlit run frontend/streamlit_app.py`
2. Navigate to **"🎴 Study Flashcards"** tab
3. Select flashcard set
4. Use navigation buttons:
   - **Show Answer** - Reveal the answer
   - **Previous/Next** - Navigate between cards
   - **Shuffle** - Randomize card order
   - **Reset** - Return to first card

### Example Usage

```python
from src.education.flashcard_generator import FlashcardGenerator

# Initialize generator
generator = FlashcardGenerator(
    model_config={"provider": "ollama", "model": "llama3"},
    max_cards_per_chunk=10,
)

# Generate from text
text = "Neural networks use backpropagation for training."
flashcards = generator.generate_flashcards(text, lecture_id="nn_basics")

# Generate from transcript file
from pathlib import Path
flashcards = generator.generate_from_transcript(
    Path("data/transcripts/lecture_01_transcript.json")
)

# Save in multiple formats
generator.save_flashcards(flashcards, Path("output.json"), format="json")
generator.save_flashcards(flashcards, Path("output.csv"), format="csv")
generator.save_flashcards(flashcards, Path("output.txt"), format="anki")
```

### Configuration

Flashcard settings in `config/config.yaml`:

```yaml
flashcards:
  max_cards_per_chunk: 10
  formats: ["json", "csv", "anki"]

flashcards_path: data/flashcards
```

---

## Phase 6 — Concept Knowledge Graph Generation

Build interactive knowledge graphs from lecture transcripts to visualize relationships between technical concepts.

```bash
python scripts/build_concept_graph.py [--limit N] [--max-viz-nodes 100]
```

### Installation

Install required dependencies:

```bash
pip install spacy networkx pyvis
python -m spacy download en_core_web_trf
```

### Pipeline Steps

| Step | Description | Output |
|---|---|---|
| 1 | Load transcripts | From `data/transcripts/` |
| 2 | Extract concepts using spaCy NER | Technical terms, noun phrases |
| 3 | Detect relationships | Co-occurrence within sentences |
| 4 | Build NetworkX graph | Nodes = concepts, Edges = relationships |
| 5 | Prune low-frequency concepts | Min frequency threshold |
| 6 | Save graph files | GraphML, JSON, CSV |
| 7 | Generate PyVis visualization | Interactive HTML |

### Outputs

| File | Description |
|---|---|
| `data/knowledge_graph/concept_graph.graphml` | NetworkX graph (GraphML format) |
| `data/knowledge_graph/concept_graph.json` | Graph nodes and edges (JSON) |
| `data/knowledge_graph/concept_graph.csv` | Concept statistics (CSV) |
| `frontend/concept_graph.html` | Interactive visualization |

### Frontend Integration

Access the concept graph from the Streamlit UI:

1. Run the pipeline to generate the graph
2. Open Streamlit: `streamlit run frontend/streamlit_app.py`
3. Click **"🔍 Explore Concept Graph"** in the sidebar
4. Interact with the visualization:
   - **Hover** over nodes to see frequency and lecture references
   - **Click and drag** nodes to rearrange
   - **Zoom** in/out with mouse wheel
   - **Navigate** using on-screen controls

### Example Usage

```python
from src.knowledge_graph.concept_extractor import ConceptExtractor
from src.knowledge_graph.graph_builder import GraphBuilder

# Extract concepts
extractor = ConceptExtractor(model_name="en_core_web_trf")
text = "Backpropagation is used to train neural networks."
concepts = extractor.extract_concepts(text)
print(concepts)  # ['backpropagation', 'neural networks']

# Build graph
builder = GraphBuilder()
builder.build_from_transcripts(
    transcript_dir=Path("data/transcripts"),
    concept_extractor=extractor,
)

# Generate visualization
builder.visualize(
    output_path=Path("frontend/concept_graph.html"),
    max_nodes=100,
)

# Get statistics
stats = builder.get_statistics()
print(f"Concepts: {stats['num_concepts']}")
print(f"Relationships: {stats['num_relationships']}")
```

### Configuration

Knowledge graph settings in `config/config.yaml`:

```yaml
knowledge_graph:
  spacy_model: "en_core_web_trf"
  min_concept_length: 3
  max_concept_length: 50
  min_frequency: 2
  max_distance: 10
  max_viz_nodes: 100
```
