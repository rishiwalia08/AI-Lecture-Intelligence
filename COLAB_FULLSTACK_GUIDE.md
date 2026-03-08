# Running Full Stack on Google Colab

This guide explains how to run both the React frontend and FastAPI backend on Google Colab.

## Quick Start

1. **Open the notebook:**
   - Upload `colab_fullstack_setup.ipynb` to Google Colab
   - Or open directly: [Open in Colab](https://colab.research.google.com)

2. **Get required tokens:**
   - **Hugging Face API Key** (free): https://huggingface.co/settings/tokens
   - **ngrok Auth Token** (free): https://dashboard.ngrok.com/get-started/your-authtoken

3. **Run all cells** in sequence (Runtime → Run all)

4. **Access your app:**
   - Frontend UI will be available at: `https://xxxxx.ngrok.io`
   - Backend API docs at: `https://yyyyy.ngrok.io/docs`

---

## What the Notebook Does

### 1. Install Node.js
Installs Node.js 20.x LTS and npm for running the React frontend.

### 2. Clone/Upload Project
Choose either:
- **Option A:** Clone from GitHub (if repo is public)
- **Option B:** Upload ZIP file of your project

### 3. Install Dependencies
- Python packages: FastAPI, ChromaDB, Hugging Face Hub, etc.
- Node packages: React, Vite, TailwindCSS, D3.js, etc.

### 4. Configure Environment
Sets up:
- `HF_API_KEY` for LLM inference
- Optional `GROQ_API_KEY` for faster responses
- Frontend `.env` with backend URL

### 5. Start Services
Runs:
- **Backend:** FastAPI on port 8000
- **Frontend:** Vite dev server on port 5173
- **ngrok:** Creates public HTTPS URLs for both

### 6. Monitor
Keeps services running and provides status updates.

---

## Architecture on Colab

```
Google Colab Runtime
├── Backend (FastAPI)
│   ├── Port: 8000
│   ├── ngrok tunnel: https://xxxxx.ngrok.io
│   └── Endpoints: /ask, /health, /knowledge_graph
│
└── Frontend (React + Vite)
    ├── Port: 5173
    ├── ngrok tunnel: https://yyyyy.ngrok.io
    └── Pages: Chat, Timeline, Graph, Flashcards, etc.
```

---

## Prerequisites

### Free Accounts
1. **Google Colab** (free tier works)
   - Sign in with Google account
   - GPU not required for this app

2. **Hugging Face** (free)
   - Create account: https://huggingface.co/join
   - Generate API token: Settings → Access Tokens → New Token
   - Copy token (starts with `hf_`)

3. **ngrok** (free tier sufficient)
   - Sign up: https://dashboard.ngrok.com/signup
   - Get auth token: https://dashboard.ngrok.com/get-started/your-authtoken
   - Copy token

### Optional
- **Groq** (for faster inference): https://console.groq.com

---

## Step-by-Step Usage

### 1. Prepare Project

**Option A: GitHub**
```bash
# Push your project to GitHub
git add .
git commit -m "Add full stack app"
git push origin main
```

**Option B: ZIP Upload**
```bash
# Create ZIP of project
cd ..
zip -r speech_rag.zip speech_rag \
  -x "speech_rag/node_modules/*" \
  -x "speech_rag/vector_db/*" \
  -x "speech_rag/.git/*"
```

### 2. Open Notebook in Colab

1. Go to: https://colab.research.google.com
2. File → Upload notebook
3. Select `colab_fullstack_setup.ipynb`

### 3. Set Tokens

In **Step 4** cell, replace:
```python
os.environ['HF_API_KEY'] = 'hf_YOUR_TOKEN_HERE'  # ⚠️ REPLACE
```

In **Step 6** cell, replace:
```python
NGROK_AUTH_TOKEN = "YOUR_NGROK_TOKEN_HERE"  # ⚠️ REPLACE
```

### 4. Run Cells

Click **Runtime → Run all** or run cells one by one:
1. Install Node.js (2-3 min)
2. Clone/upload project (1 min)
3. Install Python deps (2-3 min)
4. Set environment vars (instant)
5. Install Node deps (3-4 min)
6. Configure ngrok (instant)
7. Start backend (10 sec)
8. Configure frontend (instant)
9. Start frontend (8 sec)
10. Monitor services (keeps running)

### 5. Access Application

After Step 9 completes, you'll see:
```
🚀 SERVICES RUNNING
============================================================
📱 Frontend UI:  https://xxxxx.ngrok.io
🔧 Backend API:  https://yyyyy.ngrok.io
📚 API Docs:     https://yyyyy.ngrok.io/docs
```

Click the **Frontend UI** link to open your dashboard.

---

## Features Available

### Working Features
✅ AI Chat Assistant (/ask endpoint)
✅ System Status page
✅ About page
✅ Dark theme UI
✅ All animations and transitions

### Requires Additional Setup
⚠️ Knowledge Graph (need to build graph first)
⚠️ Flashcards (uses demo data by default)
⚠️ Summaries (uses demo data by default)
⚠️ Timeline (static demo data)
⚠️ Vector Search (synthetic demo data)

### To Enable Full Features
Run these scripts locally first, then upload results:
```bash
# Generate knowledge graph
python scripts/build_concept_graph.py

# Generate flashcards
python scripts/generate_flashcards.py

# Generate summaries
python scripts/generate_summaries.py

# Then upload data/ folder to Colab
```

---

## Performance Tips

### 1. Use Faster LLM (Optional)
Switch to Groq for 10x faster responses:
```python
# In Step 4, add:
os.environ['GROQ_API_KEY'] = 'gsk_YOUR_TOKEN'
```

Edit `config/config.yaml`:
```yaml
llm:
  provider: "groq"  # Change from "huggingface"
  model: "llama3-8b-8192"
```

### 2. Reduce Memory Usage
- Close other Colab notebooks
- Use smaller model (keep default Mistral-7B)
- Don't load large audio files

### 3. Faster Startup
- Use Option A (GitHub clone) instead of ZIP upload
- Pre-install dependencies in custom Colab runtime

### 4. Longer Sessions
- Colab free tier disconnects after ~12 hours idle
- Keep browser tab open
- Use Colab Pro for longer sessions

---

## Troubleshooting

### "Node.js not found"
```bash
# Re-run Step 1
!curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
!sudo apt-get install -y nodejs
```

### "HF_API_KEY invalid"
- Check token starts with `hf_`
- Verify token has READ permission
- Generate new token: https://huggingface.co/settings/tokens

### "ngrok tunnel failed"
- Verify auth token is correct
- Check ngrok dashboard: https://dashboard.ngrok.com/tunnels
- Free tier allows 1 agent, 40 connections/min
- Try killing and restarting: `ngrok.kill()`

### "Backend not responding"
```python
# Check backend status
!ps aux | grep uvicorn

# View logs
!tail -50 /tmp/backend.log

# Restart backend
backend_process.terminate()
# Then re-run Step 7
```

### "Frontend blank page"
```bash
# Check Vite server
!ps aux | grep vite

# Check .env file
!cat frontend/.env

# Verify VITE_API_BASE_URL is correct
```

### "Out of memory"
- Restart runtime: Runtime → Restart runtime
- Use Colab Pro (more RAM)
- Close other notebooks
- Don't upload large datasets

### "npm install fails"
```bash
# Clear cache
!cd frontend && rm -rf node_modules package-lock.json
!cd frontend && npm cache clean --force
!cd frontend && npm install
```

---

## Limitations on Colab

### Free Tier
- **Session timeout:** ~12 hours idle, 24 hours max
- **RAM:** 12-13 GB
- **Storage:** Temporary (lost on disconnect)
- **ngrok:** 1 agent, 40 req/min, random URLs

### Not Persistent
- Data lost on disconnect
- Need to re-run setup each time
- URLs change every session

### Solutions
- Use Colab Pro for longer sessions
- Save data to Google Drive
- Use ngrok paid tier for static URLs
- Deploy to Render/Railway for production

---

## Alternative: Colab Pro

### Benefits
- 25 GB RAM (vs 12 GB free)
- Longer runtimes (24+ hours)
- Faster GPUs (optional)
- Background execution

### Cost
- $10/month
- Worth it for frequent use

### Upgrade
https://colab.research.google.com/signup

---

## Saving Data to Google Drive

To persist data between sessions:

```python
# Mount Google Drive
from google.colab import drive
drive.mount('/content/drive')

# Symlink data folders
!ln -s /content/drive/MyDrive/speech_rag_data /content/speech_rag/data
!ln -s /content/drive/MyDrive/speech_rag_vectordb /content/speech_rag/vector_db

# Now data persists across sessions
```

---

## Production Deployment

For permanent hosting, use these guides:
- **Render** (recommended): See `CLOUD_DEPLOYMENT_GUIDE.md`
- **Railway:** 5-min setup, auto-deploy from Git
- **Google Cloud Run:** Serverless, pay-per-use

Colab is great for:
- Testing
- Demos
- Development
- Short-term use

Not recommended for:
- Production apps
- Public services
- 24/7 uptime

---

## Security Notes

### ⚠️ Important
- Never commit API tokens to Git
- Use Colab Secrets for tokens (Insert → Add form → Add field)
- Delete notebook after sharing
- ngrok URLs are public (anyone with URL can access)

### Best Practices
```python
# Use Colab secrets instead of hardcoding
from google.colab import userdata
os.environ['HF_API_KEY'] = userdata.get('HF_API_KEY')
os.environ['NGROK_AUTH_TOKEN'] = userdata.get('NGROK_AUTH_TOKEN')
```

---

## FAQ

**Q: Can I use GPU?**
A: Not needed. This app uses cloud LLM APIs, not local models.

**Q: How long does setup take?**
A: 10-15 minutes first time, then faster on subsequent runs.

**Q: Can multiple people use it?**
A: Yes, share the ngrok URL. Free tier allows 40 connections/min.

**Q: What if I close my browser?**
A: Colab disconnects after ~90 minutes idle. Re-run cells to restart.

**Q: Can I run without ngrok?**
A: Yes, but only accessible from Colab. ngrok provides public URLs.

**Q: Is my data secure?**
A: Data is in your Colab runtime. ngrok URLs are public. Don't upload sensitive data.

**Q: Can I use my own domain?**
A: Yes, with ngrok paid plan. Or deploy to Render/Railway with custom domain.

---

## Next Steps

1. **Test the app:**
   - Ask questions in chat
   - Explore all pages
   - Check system status

2. **Add your data:**
   - Upload lecture audio/transcripts
   - Run data pipeline
   - Build knowledge graph

3. **Deploy to cloud:**
   - Follow `CLOUD_DEPLOYMENT_GUIDE.md`
   - Get permanent URLs
   - Set up custom domain

4. **Customize:**
   - Edit UI in `frontend/src/`
   - Modify prompts in `src/llm/`
   - Add new features

---

## Support

- **Documentation:** See project README.md
- **Cloud deployment:** CLOUD_DEPLOYMENT_GUIDE.md
- **Migration guide:** HF_MIGRATION_GUIDE.md
- **Colab help:** https://research.google.com/colaboratory/faq.html
- **ngrok docs:** https://ngrok.com/docs

---

**Ready to deploy for real?**  
See [CLOUD_DEPLOYMENT_GUIDE.md](CLOUD_DEPLOYMENT_GUIDE.md) for Render, Railway, and GCP setup.
