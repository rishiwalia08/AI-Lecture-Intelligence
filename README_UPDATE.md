# README Update: Hugging Face Migration

## Section to Add to README.md (after installation section)

---

## 🤖 LLM Configuration (Phase 5)

The system supports three LLM providers for answer generation:

### ☁️ Hugging Face Inference API (Recommended for Cloud)

**Best for:** Cloud deployment, free tier, 500k+ models available.

```bash
# 1. Get API key
# Visit: https://huggingface.co/settings/tokens
# Create "User Access Token" (read permission)

# 2. Set environment variable
export HF_API_KEY="hf_your_token_here"

# 3. Verify in config.yaml
# provider: "huggingface"
# model: "mistralai/Mistral-7B-Instruct"
```

**Supported Models:**
- `mistralai/Mistral-7B-Instruct` (default, fast & accurate)
- `meta-llama/Llama-2-7b-chat-hf`
- `tiiuae/falcon-7b-instruct`
- Any instruction-tuned model on Hugging Face Hub

### ⚡ Groq API (Best for Speed)

**Best for:** Fastest inference, high throughput.

```bash
# Get API key: https://console.groq.com

export GROQ_API_KEY="gsk_your_token_here"

# In config.yaml:
# provider: "groq"
# model: "llama3-8b-8192"
```

### 💻 Ollama (Local Development)

**Best for:** Local development, no API key needed.

```bash
# Install: https://ollama.com
ollama serve

# In another terminal:
ollama pull llama3

# In config.yaml:
# provider: "ollama"
# model: "llama3"
```

---

## ☁️ Cloud Deployment

The system now supports deployment to cloud platforms:

### Quick Deploy to Render

```bash
# 1. Push to GitHub
git add .
git commit -m "Migrate to Hugging Face"
git push origin main

# 2. Visit https://render.com
# 3. Connect repository
# 4. New → Web Service
#    - Build: pip install -r requirements.txt && python -m spacy download en_core_web_sm
#    - Start: streamlit run frontend/streamlit_app.py --server.port=$PORT
# 5. Add environment variable: HF_API_KEY=hf_your_token
# 6. Deploy!
```

### Other Platforms

- **Railway.app**: https://railway.app (similar to Render)
- **Google Cloud Run**: See CLOUD_DEPLOYMENT_GUIDE.md
- **Heroku**: Paid only (free tier deprecated)

See **CLOUD_DEPLOYMENT_GUIDE.md** for detailed setup.

---

## 🧪 Validate Installation

```bash
# Test LLM integration
python test_hf_migration.py

# Expected output:
# ✅ PASS: Imports
# ✅ PASS: Config
# ✅ PASS: API Key
# ✅ PASS: LLM Loading
# ...
# ✨ All tests passed! Ready for cloud deployment.
```

---

## 📖 Migration from Ollama

If upgrading from Ollama:

1. **Update requirements:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Get Hugging Face API key:**
   ```bash
   export HF_API_KEY="hf_..."
   ```

3. **Update config (if needed):**
   - Default is already `provider: "huggingface"`
   - Or set in code: `LLMConfig(provider="huggingface")`

4. **Test:**
   ```bash
   python test_hf_migration.py
   ```

See **HF_MIGRATION_GUIDE.md** for details.

---

## 📚 Documentation

- **HF_MIGRATION_GUIDE.md** - Technical migration details
- **CLOUD_DEPLOYMENT_GUIDE.md** - Cloud deployment steps
- **MIGRATION_SUMMARY.md** - Migration overview
- **.env.example** - Environment variable template

---

## 🆘 Troubleshooting LLM

### "Invalid API Key"
```bash
# Check key is set
echo $HF_API_KEY

# Get new key: https://huggingface.co/settings/tokens
```

### "Rate Limit Exceeded"
```
Wait a few minutes and retry.
Upgrade to HF Pro for higher limits.
```

### "Model Not Found"
```
Verify model ID in config.yaml
Valid: mistralai/Mistral-7B-Instruct
```

---
