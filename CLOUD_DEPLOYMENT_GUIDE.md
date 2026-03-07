# ☁️ Cloud Deployment Guide — Hugging Face + Render

Complete guide to deploy the Speech RAG system to cloud platforms with Hugging Face API.

---

## 🎯 Quick Summary

**Old Setup (Ollama):**
- ❌ Requires local server
- ❌ CPU-only (slow)
- ❌ Can't deploy on Render/Heroku/Railway

**New Setup (Hugging Face):**
- ✅ Cloud API (serverless)
- ✅ Works anywhere
- ✅ Easy Render/Heroku/Railway deployment
- ✅ Free tier available

---

## 📋 Prerequisites

1. **Hugging Face Account**
   - Sign up: https://huggingface.co
   - Create API token: https://huggingface.co/settings/tokens
   - **Copy the token** (starts with `hf_`)

2. **Git Repository**
   - Push code to GitHub/GitLab

3. **Cloud Account** (choose one)
   - Render: https://render.com
   - Railway: https://railway.app
   - Heroku: https://heroku.com (paid)
   - Google Cloud Run: https://cloud.google.com

---

## 🚀 Deployment: Render.com (Recommended)

### Step 1: Prepare Repository

```bash
# Clone or navigate to your project
cd speech_rag

# Install dependencies locally (test)
pip install -r requirements.txt

# Test HF migration
python test_hf_migration.py --skip-api

# Commit changes
git add .
git commit -m "Migrate from Ollama to Hugging Face API"
git push origin main
```

### Step 2: Create Render Account

1. Go to https://render.com
2. Sign up with GitHub/GitLab
3. Connect your repository

### Step 3: Deploy Web Service

1. **Click "New"** → **"Web Service"**
2. **Select Repository** (your speech_rag repo)
3. **Configure:**

| Setting | Value |
|---------|-------|
| Name | `speech-rag` |
| Environment | `Python 3` |
| Region | `US (Ohio)` or closest |
| Branch | `main` |
| Build Command | `pip install -r requirements.txt && python -m spacy download en_core_web_sm` |
| Start Command | `streamlit run frontend/streamlit_app.py --server.port=$PORT` |

4. **Add Environment Variables:**
   - Click "Advanced" → "Add Environment Variable"
   - **Key:** `HF_API_KEY`
   - **Value:** `hf_your_token_here` (paste your HF token)

5. **Click "Create Web Service"**

6. **Wait** for deployment (3-5 minutes)

7. **Access** your app at: `https://speech-rag.onrender.com`

### Step 4: Backend API (Optional)

If you need the FastAPI backend:

1. **New Service** → **Web Service**
2. **Configure:**
   - Start Command: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
3. **Add same environment variables**
4. Get backend URL: `https://speech-rag-api.onrender.com`
5. Update frontend to point to backend

---

## 🚂 Deployment: Railway.app

### Step 1: Create Account

1. Go to https://railway.app
2. Sign up with GitHub
3. Connect repository

### Step 2: Deploy

```bash
# Install Railway CLI
brew install railway  # macOS
# or download from https://railway.app/cli

# Login
railway login

# Initialize project
railway init

# Set environment variable
railway variables set HF_API_KEY=hf_your_token_here

# Deploy
railway up

# Get URL
railway open
```

### Step 3: Configure

Create `railway.json`:
```json
{
  "build": {
    "builder": "heroku.buildpacks"
  },
  "deploy": {
    "startCommand": "streamlit run frontend/streamlit_app.py --server.port $PORT"
  }
}
```

---

## 🦄 Deployment: Heroku (Legacy)

Heroku free tier is gone, but you can still deploy:

```bash
# Install Heroku CLI
brew install heroku

# Login
heroku login

# Create app
heroku create speech-rag

# Set config
heroku config:set HF_API_KEY=hf_your_token_here

# Push code
git push heroku main

# View logs
heroku logs --tail
```

---

## 🔵 Deployment: Google Cloud Run

### Step 1: Create Dockerfile

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download en_core_web_sm

# Copy code
COPY . .

# Download spacy models
RUN python -m spacy download en_core_web_trf

# Expose port
EXPOSE 8501

# Set environment
ENV HF_API_KEY=${HF_API_KEY}
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_HEADLESS=true

# Run app
CMD ["streamlit", "run", "frontend/streamlit_app.py"]
```

### Step 2: Deploy

```bash
# Install Google Cloud SDK
curl https://sdk.cloud.google.com | bash

# Login
gcloud auth login

# Set project
gcloud config set project YOUR_PROJECT_ID

# Build and deploy
gcloud run deploy speech-rag \
  --source . \
  --platform managed \
  --region us-central1 \
  --set-env-vars="HF_API_KEY=hf_your_token_here" \
  --allow-unauthenticated
```

---

## 🐳 Docker Deployment (Any Platform)

### Build Image

```bash
# Build
docker build -t speech-rag .

# Run locally
docker run -e HF_API_KEY=hf_your_token_here -p 8501:8501 speech-rag

# Push to Docker Hub
docker login
docker tag speech-rag your_username/speech-rag
docker push your_username/speech-rag
```

### Deploy Container

- **AWS ECS**: Push image to ECR, deploy task
- **Digital Ocean**: Push to Digital Ocean Registry, deploy App Platform
- **Azure Container Instances**: Push to ACR, deploy
- **Kubernetes**: Use the image in deployment YAML

---

## 🔗 Connecting Components

### Frontend → Backend (if separate)

In `frontend/streamlit_app.py`, update API URL:

```python
# OLD (localhost)
api_url = "http://localhost:8000"

# NEW (cloud)
api_url = st.text_input(
    "API Base URL",
    value="https://speech-rag-api.onrender.com"
)
```

Or hardcode for production:
```python
import os
api_url = os.getenv("API_URL", "https://speech-rag-api.onrender.com")
```

### Backend → Hugging Face

Backend automatically uses `HF_API_KEY` env var:
```python
from src.llm.llm_loader import LLMConfig, load_llm

config = LLMConfig(provider="huggingface")
llm = load_llm(config)  # Uses HF_API_KEY from environment
```

---

## 🧪 Testing Deployment

### Local Test
```bash
# Test HF integration
python test_hf_migration.py

# Test full app
streamlit run frontend/streamlit_app.py
```

### Cloud Test
1. Go to deployed URL
2. Check logs for errors
3. Try asking a question

### Health Check
```bash
# For backend API
curl https://speech-rag-api.onrender.com/health

# Should return:
# {"status": "ok", "rag_ready": true}
```

---

## 📊 Monitoring

### Render Dashboard
- View logs: Service → Logs
- View metrics: Service → Metrics
- Set alerts: Settings → Alerts

### Railway Dashboard
- View logs: Deployments → Recent Deployments
- CPU/Memory usage: Monitoring

### Google Cloud
```bash
gcloud run services describe speech-rag --region us-central1
gcloud logging read "resource.type=cloud_run_revision" --limit 50
```

---

## 🆘 Troubleshooting

### "Invalid API Key"
```
Error: Invalid HF API key

Solution:
1. Check Render/Railway environment variables
2. Verify HF_API_KEY starts with "hf_"
3. Get new token from https://huggingface.co/settings/tokens
4. Update in dashboard
```

### "Rate Limited"
```
Error: Hit Hugging Face API rate limit

Solution:
1. Upgrade HF account (pro tier)
2. Use Groq as fallback
3. Wait a few minutes before retrying
```

### "Model Not Found"
```
Error: mistralai/Mistral-7B-Instruct not found

Solution:
1. Check config.yaml has correct model
2. Verify model exists on Hub
3. Try: "meta-llama/Llama-2-7b-chat-hf"
```

### "Out of Memory"
```
Error: CUDA out of memory

Solution:
1. Use smaller model (Mistral 7B works)
2. Reduce batch size in config
3. Upgrade Render/Railway tier
```

### Streamlit Doesn't Load
```
Error: Connection refused / Timeout

Solution:
1. Check logs: Service → Logs
2. Verify start command
3. Check port number (should be $PORT or 8501)
```

---

## 📈 Performance Tips

1. **API Caching**: Add Redis for response caching
2. **Batch Processing**: Process multiple queries together
3. **Model Selection**: Mistral 7B is fast & accurate
4. **Timeout**: Set reasonable timeouts (120s for LLM)
5. **Scaling**: Use Render/Railway auto-scaling

---

## 💰 Cost Breakdown

| Service | Free Tier | Cost |
|---------|-----------|------|
| Render | ✅ Free instance (pauses after 15 min) | $7/mo |
| Railway | ✅ $5 credit/month | Usage-based |
| Heroku | ❌ Paid only | $7-50/mo |
| Google Cloud Run | ✅ 2M requests free | $0.40/M requests |
| HF Inference API | ✅ Free tier | $9/mo (pro) |

**Recommended:** Render + HF Free = $0/month (with limitations)

---

## 🎓 Next Steps

1. ✅ Get HF API key
2. ✅ Set up Render account
3. ✅ Deploy to production
4. ✅ Test end-to-end
5. ✅ Monitor logs
6. ✅ Share with team

---

## 📚 References

- **Render Docs**: https://render.com/docs
- **Railway Docs**: https://railway.app/docs
- **HF Inference**: https://huggingface.co/docs/hub/inference-api
- **Streamlit Cloud**: https://streamlit.io/cloud
- **Docker**: https://docs.docker.com

---

## ❓ FAQ

**Q: Can I still use Ollama locally?**
A: Yes, but deprecated. Set `provider: "ollama"` in config.yaml

**Q: What if HF API is down?**
A: Switch to Groq: `export GROQ_API_KEY=...` and set `provider: "groq"`

**Q: Can I use a different LLM model?**
A: Yes, any Hugging Face model ID: `mistralai/Mistral-7B-Instruct`, `meta-llama/Llama-2-7b-chat-hf`, etc.

**Q: How do I update code in production?**
A: Just push to GitHub/GitLab. Render auto-deploys.

**Q: Can I add a database?**
A: Yes! Render offers PostgreSQL. Add connection string as env var.

---

🚀 **You're ready to deploy to the cloud!**
