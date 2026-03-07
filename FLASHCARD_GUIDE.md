# Flashcard Generation System Guide

Complete guide for generating and studying lecture flashcards.

---

## Overview

The flashcard generation system uses LLM to automatically create question-answer study cards from lecture transcripts. Perfect for active recall and spaced repetition learning.

---

## Quick Start

### 1. Generate Flashcards

```bash
# Generate from all transcripts
python scripts/generate_flashcards.py

# With options
python scripts/generate_flashcards.py \
  --limit 5 \
  --max-cards 15 \
  --formats json csv anki \
  --provider groq \
  --model llama3-8b-8192
```

### 2. Study Flashcards

**Option A: Streamlit UI**
```bash
streamlit run frontend/streamlit_app.py
# Navigate to "🎴 Study Flashcards" tab
```

**Option B: Import to Anki**
```bash
# 1. Open Anki
# 2. File → Import
# 3. Select: data/flashcards/all_flashcards.txt
# 4. Format: "Text separated by tabs"
```

---

## Command-Line Options

### Basic Options

- `--config PATH` - Configuration file (default: config/config.yaml)
- `--transcripts-dir PATH` - Transcripts directory
- `--output-dir PATH` - Output directory for flashcards
- `--limit N` - Process only first N transcripts

### Generation Options

- `--max-cards N` - Maximum flashcards per transcript (default: 10)
- `--formats [json csv anki]` - Output formats (default: json)

### LLM Options

- `--provider {ollama|groq}` - LLM provider
- `--model NAME` - LLM model name

### Examples

```bash
# Generate 5 flashcards per lecture, JSON only
python scripts/generate_flashcards.py --max-cards 5

# Use Groq API
python scripts/generate_flashcards.py --provider groq --model llama3-8b-8192

# Export to all formats
python scripts/generate_flashcards.py --formats json csv anki

# Process specific transcripts
python scripts/generate_flashcards.py \
  --transcripts-dir data/transcripts \
  --limit 3
```

---

## Output Formats

### JSON Format

**Location:** `data/flashcards/<lecture_id>_flashcards.json`

```json
[
  {
    "question": "What is gradient descent?",
    "answer": "An optimization algorithm that iteratively adjusts parameters to minimize a loss function.",
    "lecture_id": "ml_fundamentals",
    "topic": "Machine Learning"
  },
  {
    "question": "What is backpropagation?",
    "answer": "An algorithm for computing gradients of the loss function with respect to neural network weights.",
    "lecture_id": "ml_fundamentals",
    "topic": "Machine Learning"
  }
]
```

**Best for:** Programmatic access, web applications, API integration

### CSV Format

**Location:** `data/flashcards/<lecture_id>_flashcards.csv`

```csv
question,answer,lecture_id,topic
"What is gradient descent?","An optimization algorithm...",ml_fundamentals,Machine Learning
"What is backpropagation?","An algorithm for computing...",ml_fundamentals,Machine Learning
```

**Best for:** Spreadsheet analysis, data processing, manual review

### Anki Format

**Location:** `data/flashcards/<lecture_id>_flashcards.txt`

```
What is gradient descent?	An optimization algorithm that iteratively adjusts parameters to minimize a loss function.
What is backpropagation?	An algorithm for computing gradients of the loss function with respect to neural network weights.
```

**Format:** Tab-separated (front TAB back)

**Best for:** Direct import to Anki spaced repetition software

---

## Streamlit UI Features

### Study Interface

1. **Flashcard Set Selector**
   - Choose from individual lectures
   - Or study all flashcards combined

2. **Card Display**
   - Question shown first
   - Click "Show Answer" to reveal
   - Metadata shows topic and lecture ID

3. **Navigation Controls**
   - ⬅️ **Previous** - Go to previous card
   - ➡️ **Next** - Go to next card
   - 🔀 **Shuffle** - Randomize order
   - 🔄 **Reset** - Return to start

4. **Progress Tracking**
   - Shows current card number
   - Displays total cards in set

### Study Tips

- Start with "Show Answer" hidden
- Try to recall the answer before revealing
- Use shuffle for varied practice
- Review regularly for better retention

---

## Programmatic Usage

### Basic Generation

```python
from src.education.flashcard_generator import FlashcardGenerator
from pathlib import Path

# Initialize
generator = FlashcardGenerator(
    model_config={
        "provider": "ollama",
        "model": "llama3",
        "temperature": 0.2,
    },
    max_cards_per_chunk=10,
)

# Generate from text
text = "Neural networks use backpropagation for training."
flashcards = generator.generate_flashcards(
    text=text,
    lecture_id="nn_basics",
    topic="Deep Learning"
)

print(f"Generated {len(flashcards)} flashcards")
```

### Generate from Transcript File

```python
# Single transcript
flashcards = generator.generate_from_transcript(
    Path("data/transcripts/lecture_01_transcript.json")
)

# Multiple transcripts
all_flashcards = generator.generate_from_transcripts(
    transcript_dir=Path("data/transcripts"),
    limit=5,  # Process first 5 files
)

for lecture_id, cards in all_flashcards.items():
    print(f"{lecture_id}: {len(cards)} cards")
```

### Save Flashcards

```python
# JSON format
generator.save_flashcards(
    flashcards,
    Path("output/flashcards.json"),
    format="json"
)

# CSV format
generator.save_flashcards(
    flashcards,
    Path("output/flashcards.csv"),
    format="csv"
)

# Anki format
generator.save_flashcards(
    flashcards,
    Path("output/flashcards.txt"),
    format="anki"
)
```

### Load Flashcards

```python
# Load from JSON
flashcards = FlashcardGenerator.load_flashcards(
    Path("data/flashcards/lecture_01_flashcards.json")
)

# Use in custom application
for card in flashcards:
    print(f"Q: {card['question']}")
    print(f"A: {card['answer']}")
    print()
```

---

## Configuration

Edit `config/config.yaml`:

```yaml
# LLM settings (shared with Phase 5)
llm:
  provider: "ollama"     # "ollama" or "groq"
  model: "llama3"        # Model name
  temperature: 0.2       # Lower = more factual
  max_tokens: 512

# Flashcard settings
flashcards:
  max_cards_per_chunk: 10
  formats: ["json", "csv", "anki"]

flashcards_path: data/flashcards
```

---

## LLM Providers

### Ollama (Local)

**Pros:**
- Free and private
- No API keys needed
- Works offline

**Setup:**
```bash
# Install Ollama
# Download model
ollama pull llama3

# Use in pipeline
python scripts/generate_flashcards.py --provider ollama --model llama3
```

### Groq (Cloud API)

**Pros:**
- Very fast inference
- High-quality models
- No local compute needed

**Setup:**
```bash
# Set API key
export GROQ_API_KEY="your_key_here"

# Use in pipeline
python scripts/generate_flashcards.py --provider groq --model llama3-8b-8192
```

---

## Quality Tips

### Better Flashcards

1. **Chunk size matters**
   - Shorter chunks → more focused questions
   - Longer chunks → broader concepts

2. **Max cards per chunk**
   - 5-10 cards: Balanced approach
   - 15+ cards: More comprehensive

3. **Temperature setting**
   - 0.1-0.3: Factual, consistent
   - 0.5-0.7: Creative, varied

### Review Generated Cards

```bash
# View flashcards
cat data/flashcards/all_flashcards.json | jq

# Count flashcards
jq 'length' data/flashcards/all_flashcards.json

# Filter by topic
jq '.[] | select(.topic == "Machine Learning")' data/flashcards/all_flashcards.json
```

---

## Troubleshooting

### Issue: No flashcards generated

**Solution:**
- Check LLM is running (Ollama) or API key is set (Groq)
- Verify transcripts exist in `data/transcripts/`
- Check logs for LLM errors

### Issue: Poor quality flashcards

**Solution:**
- Lower temperature (0.1-0.2) for more factual content
- Try different model (llama3 vs mistral)
- Increase max_cards for more variety

### Issue: LLM timeout

**Solution:**
- Process fewer transcripts at once (use --limit)
- Use faster model or provider
- Increase timeout in llm_loader.py

### Issue: JSON parsing errors

**Solution:**
- System uses fallback Q&A extraction
- Check LLM output format in logs
- Try different model with better JSON adherence

---

## Import to Anki

### Step-by-Step

1. **Generate Anki format:**
   ```bash
   python scripts/generate_flashcards.py --formats anki
   ```

2. **Open Anki desktop app**

3. **Import:**
   - File → Import
   - Select: `data/flashcards/all_flashcards.txt`
   - Type: "Text separated by tabs or semicolons"
   - Field separator: Tab
   - Field 1 → Front
   - Field 2 → Back

4. **Select deck** and click Import

5. **Start studying!**

---

## Performance

- **Generation:** ~2-5 seconds per transcript (depends on LLM)
- **Ollama local:** Slower but free
- **Groq API:** Much faster (sub-second per card)
- **Output:** Instant (disk I/O)

---

## Testing

```bash
# Run flashcard generator tests
pytest tests/test_flashcard_generator.py -v

# With coverage
pytest tests/test_flashcard_generator.py -v --cov=src/education
```

---

## Best Practices

1. **Regular generation:** Regenerate after adding new lectures
2. **Version control:** Keep flashcards in git for history
3. **Quality review:** Manually review before studying
4. **Spaced repetition:** Use Anki for optimal retention
5. **Mix formats:** JSON for apps, Anki for study

---

## Integration Examples

### Web API

```python
from fastapi import FastAPI
from src.education.flashcard_generator import FlashcardGenerator

app = FastAPI()
generator = FlashcardGenerator()

@app.post("/generate_flashcards")
async def generate(text: str):
    flashcards = generator.generate_flashcards(text)
    return {"flashcards": flashcards}
```

### Custom Study App

```python
import random
from pathlib import Path
from src.education.flashcard_generator import FlashcardGenerator

# Load flashcards
cards = FlashcardGenerator.load_flashcards(
    Path("data/flashcards/all_flashcards.json")
)

# Shuffle for practice
random.shuffle(cards)

# Simple CLI study session
for i, card in enumerate(cards, 1):
    print(f"\n[{i}/{len(cards)}] {card['question']}")
    input("Press Enter to reveal answer...")
    print(f"→ {card['answer']}")
    input("Press Enter for next card...")
```

---

## File Structure

```
data/flashcards/
├── lecture_01_flashcards.json     # Individual lecture (JSON)
├── lecture_01_flashcards.csv      # Individual lecture (CSV)
├── lecture_01_flashcards.txt      # Individual lecture (Anki)
├── lecture_02_flashcards.*        # ...
├── all_flashcards.json            # Combined (JSON)
├── all_flashcards.csv             # Combined (CSV)
└── all_flashcards.txt             # Combined (Anki)
```

---

## Summary

✅ **Generation:** LLM-powered Q&A extraction  
✅ **Storage:** JSON, CSV, Anki formats  
✅ **Study:** Streamlit UI with navigation  
✅ **Export:** Direct Anki import  
✅ **Flexible:** Configurable and scriptable  

Perfect for active learning from lecture content!
