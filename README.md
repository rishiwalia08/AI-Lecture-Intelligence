# AI Lecture Intelligence

### Speech-to-RAG Lecture Search System

AI Lecture Intelligence is an AI-powered system that allows students to search lecture recordings using natural language or voice and instantly locate the exact moment where a concept is explained.

The platform combines **Speech Recognition, Retrieval Augmented Generation (RAG), Vector Databases, and Knowledge Graphs** to build an interactive AI assistant for educational content.

---

# Overview

Students often spend hours rewatching lectures to find a specific explanation.
This system solves that problem by enabling **semantic search across lecture recordings**.

Example query:

> “What is gradient descent?”

The system retrieves:

* the most relevant lecture segment
* an AI-generated explanation
* the exact lecture timestamp

---

# Key Features

• Speech-based lecture search
• Timestamp-level lecture retrieval
• Retrieval Augmented Generation (RAG) answers
• Hybrid semantic + keyword search
• Concept knowledge graph visualization
• Automatic flashcard generation
• Lecture summarization for revision
• Modular AI pipeline architecture

---

# System Architecture

```
Lecture Audio
      ↓
Speech Recognition (Whisper)
      ↓
Timestamped Transcripts
      ↓
Chunking & Embeddings (BGE-M3)
      ↓
Vector Database (ChromaDB)
      ↓
Hybrid Retrieval + Reranking
      ↓
LLM Answer Generation (Llama 3)
      ↓
Interactive Interface (React Dashboard)
```

Additional modules:

```
Concept Knowledge Graph
Flashcard Generation
Lecture Summarization
```

---

# Technology Stack

## Machine Learning

* Whisper (Speech Recognition)
* Llama 3 (LLM)
* BGE-M3 (Embeddings)
* BGE Reranker

## Backend

* Python
* FastAPI

## Retrieval

* ChromaDB
* BM25
* LangChain

## NLP

* spaCy
* NetworkX

## Frontend

* React + Vite
* TailwindCSS + Framer Motion
* D3.js + Recharts

---

# Project Structure

```
speech_rag/
│
├── config/
│   └── config.yaml
│
├── data/
│   ├── raw_audio/
│   ├── processed_audio/
│   ├── transcripts/
│   ├── segments/
│   ├── pdfs/
│   └── dataset_metadata.csv
│
├── datasets/
│   ├── tedlium/
│   ├── librispeech/
│   └── commonvoice_indian/
│
├── src/
│   ├── asr/
│   ├── data_ingestion/
│   ├── audio_processing/
│   ├── anonymization/
│   ├── embedding/
│   ├── retrieval/
│   ├── llm/
│   ├── knowledge_graph/
│   └── education/
│
├── scripts/
│   ├── run_phase1_pipeline.py
│   ├── run_phase2_asr.py
│   ├── run_phase3_indexing.py
│   ├── generate_flashcards.py
│   ├── generate_summaries.py
│   └── build_concept_graph.py
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│
├── backend/
│
├── tests/
│
├── logs/
│
├── requirements.txt
└── README.md
```

---

# Installation

Clone the repository

```
git clone https://github.com/yourusername/AI-Lecture-Intelligence.git
cd AI-Lecture-Intelligence
```

Install dependencies

```
pip install -r requirements.txt
```

Install spaCy models

```
python -m spacy download en_core_web_sm
python -m spacy download en_core_web_trf
```

---

# Running the System

### Phase 1 — Data Preparation

```
python scripts/run_phase1_pipeline.py
```

This step:

* loads dataset metadata
* normalizes audio to **16 kHz mono WAV**
* validates dataset structure

---

### Phase 2 — Whisper Transcription

```
python scripts/run_phase2_asr.py
```

This step:

* transcribes audio
* produces timestamped segments
* saves transcripts as JSON

Example output:

```
data/transcripts/lecture_01_transcript.json
```

---

### Phase 3 — Vector Indexing

```
python scripts/run_phase3_indexing.py
```

This step:

* chunks transcripts
* generates embeddings
* stores vectors in ChromaDB

---

### Launch the Interface

Start backend:

```
uvicorn backend.app.main:app --reload
```

Run React frontend:

```
cd frontend
npm install
npm run dev
```

Set frontend API URL in `frontend/.env` if needed:

```
VITE_API_BASE_URL=http://localhost:8000
```

---

# Example Query

Input:

```
What is backpropagation?
```

Output:

```
Answer:
Backpropagation is a training algorithm used in neural networks
to update weights using gradient descent.

Source:
Lecture 7 — Timestamp 14:02
```

---

# Flashcard Generation

Generate study flashcards from lecture transcripts.

```
python scripts/generate_flashcards.py
```

Example flashcard:

```
Q: What is gradient descent?

A: An optimization algorithm used to minimize loss during training.
```

Export formats:

* JSON
* CSV
* Anki

---

# Concept Knowledge Graph

Build concept relationships across lectures.

```
python scripts/build_concept_graph.py
```

This produces:

```
data/knowledge_graph/concept_graph.graphml
frontend/concept_graph.html
```

Example concept graph:

```
Neural Networks
   |
   |--- Backpropagation
   |--- Gradient Descent
   |--- Activation Functions
```

---

# Running Tests

Run the full test suite:

```
pytest tests/ -v
```

With coverage:

```
pytest tests/ --cov=src
```

---

# Logs & Metrics

```
logs/pipeline.log
logs/asr_pipeline.log
logs/asr_metrics.csv
```

Metrics tracked:

* transcription time
* audio duration
* realtime factor
* segment counts

---

# Roadmap

Phase 1 — Data ingestion & preprocessing
Phase 2 — Whisper transcription
Phase 3 — Vector indexing
Phase 4 — Hybrid retrieval
Phase 5 — RAG answer generation
Phase 6 — Concept knowledge graph
Phase 7 — Flashcard generation
Phase 8 — Lecture summarization

---

# Future Improvements

• Voice-to-voice AI tutor
• Lecture timeline generation
• Multi-course search
• Slide extraction from videos
• Personalized study recommendations

---

# Documentation Note

All previous phase-wise markdown guides/checklists were consolidated into this single README.

---

# Author

**Rishi Walia**
B.Tech CSE (AI & ML)
VIT Chennai

---

# License

MIT License
