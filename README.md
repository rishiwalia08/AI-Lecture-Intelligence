# Lecture Intelligence System

Production-ready AI system to ingest lecture videos (YouTube or uploaded), transcribe, chunk, index, summarize, and answer grounded questions with exact timestamps.

## What this build includes

- ✅ Video ingestion from YouTube URL or local upload
- ✅ Audio extraction via `ffmpeg`
- ✅ ASR transcription via `faster-whisper`
- ✅ Transcript cleaning + time-aware chunking
- ✅ Embeddings + vector DB (`ChromaDB`)
- ✅ RAG Q&A over transcript chunks
- ✅ Topic semantic search
- ✅ Timestamp-aware responses + clickable YouTube deep links
- ✅ Smart summary: TL;DR, detailed notes, key points, topic breakdown
- ✅ Minimal clean Next.js interface

---

## Architecture

```text
Video URL / Upload
    ↓
Video Ingestion (yt-dlp / upload)
    ↓
Audio Extraction (ffmpeg)
    ↓
ASR (faster-whisper)
    ↓
Cleaned Timestamped Segments
    ↓
Semantic Chunking (time + length boundaries)
    ↓
Embeddings (Sentence Transformers or OpenAI)
    ↓
ChromaDB per-video index
    ↓
RAG QA + Topic Search + Summarization
    ↓
Frontend with clickable timestamps
```

---

## Folder structure

```text
backend/
  api/
    routes.py
    schemas.py
  services/
    transcription.py
    embeddings.py
    rag.py
    summarizer.py
    llm.py
    pipeline.py
  db/
    repository.py
  utils/
    time_utils.py
    video_utils.py
  main.py
  config.py
  requirements.txt

frontend/
  components/
  pages/
  styles/
  package.json

README.md
```

---

## Backend setup (FastAPI)

### 1) Prerequisites

- Python 3.10+
- `ffmpeg` installed and available in PATH
- (for YouTube ingestion) `yt-dlp` available (installed via pip in requirements)

Install ffmpeg on macOS:

```bash
brew install ffmpeg
```

### 2) Install dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 3) Run API

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

---

## Frontend setup (Next.js)

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Open: `http://localhost:3000`

---

## API Endpoints

### Ingest (YouTube or upload)
`POST /api/v1/videos/ingest`

- Form fields:
  - `youtube_url` (optional)
  - `title` (optional)
  - `file` (optional video file)
- Provide either `youtube_url` or `file`

### List videos
`GET /api/v1/videos`

### Get video details
`GET /api/v1/videos/{video_id}`

### Get summary
`GET /api/v1/videos/{video_id}/summary`

### Get transcript chunks
`GET /api/v1/videos/{video_id}/transcript`

### Ask question (RAG)
`POST /api/v1/videos/{video_id}/qa`

```json
{
  "question": "Explain overfitting from this lecture"
}
```

Response includes:
- `answer`
- `references[]` with `start_time`, `end_time`, human-readable timestamp, and `youtube_link` (if source is YouTube)

### Semantic topic search
`POST /api/v1/videos/{video_id}/search`

```json
{
  "query": "gradient descent"
}
```

---

## Example output shape (QA)

```json
{
  "answer": "Overfitting occurs when the model memorizes training examples...",
  "references": [
    {
      "chunk_id": "chunk_14",
      "text": "...",
      "start_time": 754.2,
      "end_time": 850.0,
      "timestamp": "12:34 - 14:10",
      "youtube_link": "https://youtube.com/watch?v=VIDEO_ID&t=754"
    }
  ]
}
```

---

## Design decisions (step-by-step)

1. **Time-first transcript representation**
   - Every chunk stores `start_time` and `end_time`.
   - Enables direct timestamp navigation and YouTube deep links.

2. **Chunking for long videos**
   - Chunk boundaries combine pause-based splitting and max character threshold.
   - This improves retrieval relevance and keeps context windows stable.

3. **RAG grounding**
   - Answers are generated from retrieved transcript chunks only.
   - Responses always include references with timestamps.

4. **Model flexibility**
   - Embeddings backend can be switched:
     - `sentence-transformers` (default, local)
     - `openai` (higher quality if API key is provided)

5. **Production-leaning persistence**
   - ChromaDB persisted to disk.
   - Metadata + artifacts saved under backend `db/`.

---

## Advanced features status

- ✅ Multi-video architecture (each video has dedicated collection + metadata)
- ✅ Topic segmentation (time-aware chunking)
- ✅ YouTube timestamp deep links
- ✅ Grounded QA citations
- ⏳ Per-video chat history persistence (easy next step)
- ⏳ Bookmarks/notes API (easy next step)
- ⏳ Exact sentence highlighting in transcript viewer

---

## Production notes

- For heavy workloads, move ingestion into background workers (Celery/RQ).
- Use GPU Whisper for faster transcription.
- Add auth + rate limits for public deployment.
- Add caching and batched retrieval for long multi-hour videos.
- Use a managed vector store (Pinecone/Weaviate) for scale.

---

## Quick smoke test

1. Start backend and frontend.
2. Ingest a YouTube lecture URL.
3. Ask: *"Explain gradient descent from this lecture"*.
4. Verify returned timestamps and clickable links.
5. Search topic and verify top chunks/time ranges.

---

## License

MIT
