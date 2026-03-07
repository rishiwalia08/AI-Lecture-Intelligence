# 🚀 Ollama → Hugging Face API Migration Guide

## ✅ What Was Changed

### 1. **New Hugging Face Client** (`src/llm/hf_client.py`)
Created a lightweight HF Inference API wrapper with:
- Cloud-deployable LLM inference
- Error handling for API key, rate limits, network issues
- Health check functionality
- Proper message formatting for instruction-tuned models

### 2. **Updated LLM Loader** (`src/llm/llm_loader.py`)
**Changes:**
- Added `HuggingFaceProvider` class (new default)
- Updated `LLMConfig` defaults: `provider="huggingface"`, `model="mistralai/Mistral-7B-Instruct"`
- Deprecated `OllamaProvider` (kept for backwards compatibility)
- Updated `load_llm()` to support 3 providers: huggingface, groq, ollama

**Backwards Compatibility:**
- Can still use Ollama locally (with deprecation warning)
- Can still use Groq API
- Ollama code remains but logs warning

### 3. **Config Update** (`config/config.yaml`)
```yaml
# OLD
llm:
  provider: "ollama"
  model: "llama3"

# NEW
llm:
  provider: "huggingface"
  model: "mistralai/Mistral-7B-Instruct"
```

### 4. **Dependencies** (`requirements.txt`)
**Added:**
```
huggingface_hub>=0.19.0     # NEW
```

**Kept:**
```
groq>=0.8.0                 # Alternative
```

**Removed:**
- `ollama` SDK (optional, kept for backwards compatibility)

---

## 🎯 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Get Hugging Face API Key
1. Go to: https://huggingface.co/settings/tokens
2. Create new **User Access Token** (read permission)
3. Copy the token

### 3. Set Environment Variable
```bash
# Linux/Mac
export HF_API_KEY="hf_your_token_here"

# Windows
set HF_API_KEY=hf_your_token_here

# Or add to .env file:
echo "HF_API_KEY=hf_your_token_here" >> .env
```

### 4. Test Connection
```python
from src.llm.llm_loader import LLMConfig, load_llm

config = LLMConfig(provider="huggingface", model="mistralai/Mistral-7B-Instruct")
llm = load_llm(config)

messages = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "What is AI?"}
]
response = llm.generate(messages)
print(response.content)
```

### 5. Run Full Pipeline
```bash
# Phase 3: Embedding
python scripts/run_phase3_indexing.py

# Phase 5: RAG (now uses HF API)
python scripts/test_rag_system.py

# Phase 7: Flashcards (now uses HF API)
python scripts/generate_flashcards.py

# Phase 8: Summaries (now uses HF API)
python scripts/generate_summaries.py

# Start app
streamlit run frontend/streamlit_app.py
```

---

## 🌐 Cloud Deployment

### Render.com
```bash
# Add environment variable in Render dashboard:
HF_API_KEY = hf_your_token_here

# Deploy
git push heroku main
```

### Railway.app
```yaml
# railway.json
{
  "build": {
    "builder": "heroku.buildpacks"
  },
  "deploy": {
    "startCommand": "streamlit run frontend/streamlit_app.py"
  }
}

# Set env vars in Railway dashboard
```

### Google Cloud Run
```bash
# Create .env.yaml
HF_API_KEY=hf_your_token_here

# Deploy
gcloud run deploy --env-vars-file=.env.yaml
```

### Docker
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV HF_API_KEY=${HF_API_KEY}
CMD ["streamlit", "run", "frontend/streamlit_app.py"]
```

```bash
# Build and run
docker build -t speech-rag .
docker run -e HF_API_KEY=hf_your_token_here -p 8501:8501 speech-rag
```

---

## 📊 Model Comparison

| Feature | Hugging Face | Groq | Ollama |
|---------|--------------|------|--------|
| **Deployment** | Cloud | Cloud | Local |
| **Setup** | Easy (API key) | Easy (API key) | Hard (server) |
| **Speed** | Fast | ⚡ Fastest | Slow (CPU) |
| **Cost** | Free tier | Free tier | $0 |
| **Models** | 500k+ | 3 models | Any |
| **Best For** | Production | Speed | Dev |

---

## 🔧 Provider Comparison

### Hugging Face Inference API
```python
config = LLMConfig(provider="huggingface", model="mistralai/Mistral-7B-Instruct")
```
**Pros:**
- Cloudready
- 500k+ models available
- Free tier generous
- Easy deployment

**Cons:**
- Slightly slower than Groq
- Rate limits on free tier

### Groq API
```python
config = LLMConfig(provider="groq", model="llama3-8b-8192")
```
**Pros:**
- Fastest inference
- Very responsive

**Cons:**
- Fewer model options
- Limited free tier

### Ollama (Local)
```python
config = LLMConfig(provider="ollama", model="llama3")
```
**Pros:**
- No API key needed
- Complete control
- Works offline

**Cons:**
- Slow (CPU only)
- Not cloud-friendly
- Requires local server

---

## 🚨 Troubleshooting

### "Invalid HF API Key"
```bash
# Check your token
echo $HF_API_KEY

# Get new token
# https://huggingface.co/settings/tokens
```

### "Rate Limited"
```
Wait a few minutes, then retry.
Upgrade to HF Pro for higher limits.
```

### "Model Not Found"
```python
# Valid models:
"mistralai/Mistral-7B-Instruct"
"meta-llama/Llama-2-7b-chat-hf"
"tiiuae/falcon-7b-instruct"

# Check available models:
from huggingface_hub import list_models
models = list_models(filter="instruct")
```

### "Network Error"
```bash
# Check internet connection
ping huggingface.co

# Use Groq as fallback
export GROQ_API_KEY=...
config = LLMConfig(provider="groq")
```

---

## 📝 Updated File Summary

| File | Changes |
|------|---------|
| `src/llm/hf_client.py` | **NEW** - HF Inference API wrapper |
| `src/llm/llm_loader.py` | Added `HuggingFaceProvider`, updated defaults |
| `config/config.yaml` | Changed LLM provider to "huggingface" |
| `requirements.txt` | Added `huggingface_hub`, kept `groq` |

---

## ✨ Features Unaffected

All existing features work seamlessly:
- ✅ Text queries with RAG
- ✅ Audio queries with speech recognition
- ✅ Flashcard generation
- ✅ Lecture summarization
- ✅ Knowledge graph generation
- ✅ Vector database indexing
- ✅ Hybrid retrieval (BM25 + semantic)

---

## 🔄 Fallback to Ollama (if needed)

To temporarily use Ollama:
```bash
# Start Ollama server
ollama serve

# In another terminal
export OLLAMA_API_KEY=...
python -c "
from src.llm.llm_loader import LLMConfig, load_llm
config = LLMConfig(provider='ollama', model='llama3')
llm = load_llm(config)
"
```

---

## 📚 Example Usage

### RAG Answer Generation
```python
from src.llm.llm_loader import LLMConfig, load_llm
from src.llm.answer_generator import AnswerGenerator

# Load HF model
config = LLMConfig(provider="huggingface")
llm = load_llm(config)

# Generate answer
generator = AnswerGenerator(llm)
result = generator.generate(
    query="What is backpropagation?",
    chunks=retrieved_chunks
)
print(result.answer)
```

### Flashcard Generation
```python
from src.education.flashcard_generator import FlashcardGenerator

config = LLMConfig(provider="huggingface")
llm = load_llm(config)

generator = FlashcardGenerator(llm)
flashcards = generator.generate_flashcards(transcript)
```

### Lecture Summarization
```python
from src.education.lecture_summarizer import LectureSummarizer

config = LLMConfig(provider="huggingface")
llm = load_llm(config)

summarizer = LectureSummarizer(llm)
summary = summarizer.summarize_lecture(transcript_text)
```

---

## 🎉 Next Steps

1. ✅ Install dependencies: `pip install -r requirements.txt`
2. ✅ Get HF API key: https://huggingface.co/settings/tokens
3. ✅ Set environment: `export HF_API_KEY=hf_...`
4. ✅ Test: `python scripts/test_rag_system.py`
5. ✅ Deploy to cloud (Render, Railway, Cloud Run, etc.)

---

## 📞 Support

- **HF Docs**: https://huggingface.co/docs/hub/inference-api
- **Groq Docs**: https://console.groq.com/docs
- **Project Repo**: Check README.md for full documentation
