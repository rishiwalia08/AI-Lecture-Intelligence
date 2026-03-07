"""
frontend/streamlit_app.py
---------------------------
Interactive Lecture Intelligence — Streamlit Frontend

Usage
-----
    streamlit run frontend/streamlit_app.py

Requires the FastAPI backend to be running:
    uvicorn backend.app.main:app --reload --port 8000
"""

from __future__ import annotations

import io
import time
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

# ──────────────────────────────────────────────────────────────
# Page setup
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Interactive Lecture Intelligence",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────
# Custom CSS — premium dark theme
# ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Dark gradient background */
.stApp {
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    color: #e8e8f0;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: rgba(255,255,255,0.05);
    backdrop-filter: blur(10px);
    border-right: 1px solid rgba(255,255,255,0.1);
}

/* Buttons */
div.stButton > button {
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 0.6rem 1.5rem;
    font-weight: 600;
    font-size: 1rem;
    transition: all 0.3s ease;
    width: 100%;
}
div.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(102,126,234,0.5);
}

/* Input box */
.stTextArea textarea, .stTextInput input {
    background: rgba(255,255,255,0.07) !important;
    border: 1px solid rgba(255,255,255,0.2) !important;
    border-radius: 10px !important;
    color: #e8e8f0 !important;
    font-size: 1rem !important;
}

/* Answer card */
.answer-card {
    background: rgba(102,126,234,0.12);
    border-left: 4px solid #667eea;
    border-radius: 12px;
    padding: 1.5rem;
    margin: 1rem 0;
    animation: fadeIn 0.5s ease;
}
/* Source card */
.source-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin: 0.5rem 0;
    transition: all 0.2s ease;
}
.source-card:hover { border-color: #667eea; transform: translateX(4px); }
.badge {
    display: inline-block;
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white;
    padding: 0.2rem 0.7rem;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
    margin-right: 0.5rem;
}
.time-badge {
    display: inline-block;
    background: rgba(100,255,180,0.15);
    color: #64ffb4;
    padding: 0.2rem 0.7rem;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 500;
}

@keyframes fadeIn { from { opacity:0; transform: translateY(10px); } to { opacity:1; transform: translateY(0); } }

/* Title */
.hero-title {
    text-align: center;
    font-size: 2.4rem;
    font-weight: 700;
    background: linear-gradient(135deg, #667eea, #a78bfa, #64ffb4);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.2rem;
}
.hero-sub {
    text-align: center;
    color: rgba(255,255,255,0.5);
    font-size: 1rem;
    margin-bottom: 2rem;
}
/* Metric chips */
.metric-row { display: flex; gap: 1rem; margin: 0.5rem 0; }
.metric-chip {
    background: rgba(255,255,255,0.06);
    border-radius: 8px;
    padding: 0.4rem 0.9rem;
    font-size: 0.82rem;
    color: rgba(255,255,255,0.6);
}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# Sidebar configuration
# ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    api_url = st.text_input("API Base URL", value="http://localhost:8000")
    top_k   = st.slider("Results to retrieve", 1, 10, 5)
    lecture_filter = st.text_input("Lecture filter (optional)", placeholder="e.g. lecture_07")
    lecture_filter = lecture_filter.strip() or None

    st.markdown("---")
    st.markdown("### 🏥 API Status")
    if st.button("Check API health"):
        try:
            r = requests.get(f"{api_url}/health", timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data.get("rag_ready"):
                    st.success("✅ API ready")
                else:
                    st.warning(f"⏳ {data.get('message', 'RAG initialising…')}")
            else:
                st.error(f"❌ Status {r.status_code}")
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot reach API. Start it with:\n```\nuvicorn backend.app.main:app --reload\n```")
    
    st.markdown("---")
    st.markdown("### 🧠 Knowledge Graph")
    if st.button("🔍 Explore Concept Graph", use_container_width=True):
        import webbrowser
        import os
        graph_path = os.path.join(os.path.dirname(__file__), "concept_graph.html")
        if os.path.exists(graph_path):
            webbrowser.open(f"file://{os.path.abspath(graph_path)}")
            st.success("✅ Opening concept graph...")
        else:
            st.warning("⚠️ Concept graph not yet generated. Run:\n```\npython scripts/build_concept_graph.py\n```")

    st.markdown("---")
    st.markdown(
        "**Interactive Lecture Intelligence**  \n"
        "Speech-RAG System • Phase 6  \n"
        "`FastAPI + Streamlit`",
        unsafe_allow_html=False,
    )


# ──────────────────────────────────────────────────────────────
# Hero header
# ──────────────────────────────────────────────────────────────
st.markdown('<div class="hero-title">🎓 Interactive Lecture Intelligence</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Ask questions about your lecture recordings and get timestamped answers.</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────
# Session state
# ──────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history: List[Dict[str, Any]] = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
def _call_ask(query: str) -> Optional[Dict]:
    """POST /ask and return the JSON response dict, or None on error."""
    try:
        r = requests.post(
            f"{api_url}/ask",
            json={
                "query": query,
                "top_k": top_k,
                "lecture_filter": lecture_filter,
            },
            timeout=120,
        )
        if r.status_code == 200:
            return r.json()
        else:
            detail = r.json().get("detail", r.text)
            st.error(f"❌ API error {r.status_code}: {detail}")
            return None
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot reach API. Is the backend running?")
        return None
    except Exception as exc:  # noqa: BLE001
        st.error(f"❌ Unexpected error: {exc}")
        return None


def _call_speech(audio_bytes: bytes, filename: str = "audio.wav") -> Optional[Dict]:
    """POST /speech_query and return the JSON response dict."""
    try:
        r = requests.post(
            f"{api_url}/speech_query",
            files={"audio": (filename, io.BytesIO(audio_bytes), "audio/wav")},
            data={"top_k": top_k, "lecture_filter": lecture_filter or ""},
            timeout=180,
        )
        if r.status_code == 200:
            return r.json()
        else:
            detail = r.json().get("detail", r.text)
            st.error(f"❌ Speech API error {r.status_code}: {detail}")
            return None
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot reach API.")
        return None
    except Exception as exc:  # noqa: BLE001
        st.error(f"❌ Unexpected error: {exc}")
        return None


def _display_result(result: Dict, transcribed: str = "") -> None:
    """Render answer + sources in the UI."""
    answer  = result.get("answer", "No answer returned.")
    sources = result.get("sources", [])
    elapsed = result.get("query_time_s", 0)

    # Metrics row
    st.markdown(
        f'<div class="metric-row">'
        f'<span class="metric-chip">⏱ {elapsed:.2f}s</span>'
        f'<span class="metric-chip">📚 {len(sources)} sources</span>'
        f'{"<span class=\"metric-chip\">🎤 Audio query</span>" if transcribed else ""}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Transcribed query (audio mode)
    if transcribed:
        st.markdown(f"> **Transcribed:** _{transcribed}_")

    # Answer
    st.markdown(f'<div class="answer-card">📖 {answer}</div>', unsafe_allow_html=True)

    # Sources
    if sources:
        st.markdown("### 📍 Lecture Sources")
        for s in sources:
            lid  = s.get("lecture_id", "?")
            ts   = s.get("timestamp", "??:??")
            st_s = s.get("start_time", 0)
            en_s = s.get("end_time", 0)
            st.markdown(
                f'<div class="source-card">'
                f'<span class="badge">🎬 {lid}</span>'
                f'<span class="time-badge">🕐 {ts}</span>'
                f' &nbsp; {st_s:.0f}s → {en_s:.0f}s'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Video player — seeks to first source timestamp
        if sources:
            first = sources[0]
            start_sec = int(first.get("start_time", 0))
            lid       = first.get("lecture_id", "")
            # If a video file exists at data/raw_audio/<lecture_id>.mp4, show it
            video_path = f"data/raw_audio/{lid}.mp4"
            st.markdown("---")
            st.markdown("### 🎬 Lecture Segment Player")
            st.info(
                f"▶ Jump to **{first.get('timestamp', '??:??')}** in _{lid}_  "
                f"(seek to {start_sec}s)"
            )
            # Try to show video — useful when lecture video files are present
            import os
            if os.path.exists(video_path):
                st.video(video_path, start_time=start_sec)
            else:
                st.caption(
                    f"Place your lecture video at `{video_path}` "
                    f"and it will automatically play from {first.get('timestamp')}."
                )
    else:
        st.info("ℹ️ No lecture sources found for this query.")


# ──────────────────────────────────────────────────────────────
# Main query tabs
# ──────────────────────────────────────────────────────────────
tab_text, tab_audio, tab_summary, tab_flashcards, tab_history = st.tabs(
    ["💬 Text Query", "🎤 Audio Query", "📝 Lecture Summary", "🎴 Study Flashcards", "📜 History"]
)

# ── Text query ────────────────────────────────────────────────
with tab_text:
    st.markdown("### Ask a Question")
    user_query = st.text_area(
        "Your question",
        placeholder="e.g. What is gradient descent? How does backpropagation work?",
        height=100,
        label_visibility="collapsed",
    )

    # Example questions
    st.markdown("**Quick examples:**")
    ex_cols = st.columns(3)
    examples = [
        "What is gradient descent?",
        "Explain backpropagation",
        "What is the KMP algorithm?",
    ]
    for col, ex in zip(ex_cols, examples):
        if col.button(ex, key=f"ex_{ex}"):
            user_query = ex

    col1, col2 = st.columns([3, 1])
    ask_btn = col1.button("🔍 Ask", key="ask_text", type="primary")
    col2.button("🗑 Clear", key="clear_text", on_click=lambda: st.session_state.update({"last_result": None}))

    if ask_btn:
        if not user_query or not user_query.strip():
            st.warning("⚠️ Please enter a question.")
        else:
            with st.spinner("🤔 Thinking…"):
                result = _call_ask(user_query.strip())
            if result:
                st.session_state.last_result = result
                st.session_state.history.append({"query": user_query, "result": result, "type": "text"})

    if st.session_state.last_result:
        st.markdown("---")
        _display_result(st.session_state.last_result)


# ── Audio query ───────────────────────────────────────────────
with tab_audio:
    st.markdown("### 🎤 Record or Upload Audio")
    st.info(
        "**Option 1**: Record using the microphone widget below.  \n"
        "**Option 2**: Upload a pre-recorded audio file (WAV, MP3, M4A, OGG, WebM)."
    )

    # Try audio recorder component (optional: pip install audio-recorder-streamlit)
    audio_bytes_recorded = None
    try:
        from audio_recorder_streamlit import audio_recorder  # type: ignore[import]
        st.markdown("**🎙 Record:**")
        audio_bytes_recorded = audio_recorder(
            text="Click to record",
            recording_color="#667eea",
            neutral_color="#a78bfa",
            icon_size="2x",
        )
    except ImportError:
        st.caption(
            "ℹ️ Install `audio-recorder-streamlit` for in-browser recording:  \n"
            "`pip install audio-recorder-streamlit`"
        )

    # File uploader fallback
    st.markdown("**📁 Or upload a file:**")
    uploaded_audio = st.file_uploader(
        "Upload audio", type=["wav", "mp3", "ogg", "webm", "m4a"],
        label_visibility="collapsed",
    )

    if st.button("🎤 Submit Audio", key="ask_audio", type="primary"):
        audio_data: Optional[bytes] = None
        fname = "audio.wav"

        if audio_bytes_recorded:
            audio_data = audio_bytes_recorded
        elif uploaded_audio is not None:
            audio_data = uploaded_audio.read()
            fname = uploaded_audio.name
        else:
            st.warning("⚠️ Please record or upload an audio file first.")

        if audio_data:
            with st.spinner("🎙 Transcribing and thinking…"):
                result = _call_speech(audio_data, fname)
            if result:
                transcribed = result.get("transcribed_query", "")
                st.session_state.last_result = result
                st.session_state.history.append({
                    "query": transcribed,
                    "result": result,
                    "type": "audio",
                })
                st.markdown("---")
                _display_result(result, transcribed=transcribed)


# ── Lecture Summary ───────────────────────────────────────────
with tab_summary:
    st.markdown("### 📝 Lecture Summary")
    
    # Load summaries
    summary_dir = Path("data/summaries")
    
    if not summary_dir.exists() or not list(summary_dir.glob("*.json")):
        st.info(
            "📚 No summaries available yet.\n\n"
            "Generate summaries by running:\n"
            "```\n"
            "python scripts/generate_summaries.py\n"
            "```"
        )
    else:
        # Summary file selector
        summary_files = sorted(summary_dir.glob("*.json"))
        file_options = [f.stem.replace("_summary", "") for f in summary_files]
        
        if file_options:
            selected_lecture = st.selectbox(
                "Select lecture:",
                options=file_options,
                key="summary_file_selector"
            )
            
            # Load selected summary
            selected_path = summary_dir / f"{selected_lecture}_summary.json"
            try:
                import json
                with open(selected_path, "r", encoding="utf-8") as f:
                    summary_data = json.load(f)
                
                # Display lecture info
                st.markdown(f"## 🎓 {selected_lecture.replace('_', ' ').title()}")
                
                if "topic" in summary_data:
                    st.markdown(f"**Topic:** {summary_data['topic']}")
                
                st.markdown("---")
                
                # Display summary
                summary_text = summary_data.get("summary", "No summary available.")
                if summary_text:
                    st.markdown(
                        f'<div class="answer-card">'
                        f'<h4>📖 Summary</h4>'
                        f'{summary_text}'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                
                # Display key concepts
                key_concepts = summary_data.get("key_concepts", [])
                if key_concepts:
                    st.markdown("### 🔑 Key Concepts")
                    cols = st.columns(2)
                    for i, concept in enumerate(key_concepts):
                        col_idx = i % 2
                        with cols[col_idx]:
                            st.markdown(
                                f'<div class="source-card">'
                                f'<span class="badge">📌</span> {concept}'
                                f'</div>',
                                unsafe_allow_html=True
                            )
                
                # Display definitions
                definitions = summary_data.get("definitions", {})
                if definitions:
                    st.markdown("### 📖 Important Definitions")
                    for term, definition in definitions.items():
                        with st.expander(f"**{term}**"):
                            st.markdown(definition)
                
                # Metrics
                st.markdown("---")
                metric_cols = st.columns(3)
                with metric_cols[0]:
                    st.metric("Words", len(summary_text.split()))
                with metric_cols[1]:
                    st.metric("Key Concepts", len(key_concepts))
                with metric_cols[2]:
                    st.metric("Definitions", len(definitions))
                
            except Exception as e:
                st.error(f"Error loading summary: {e}")
        else:
            st.warning("No summary files found.")


# ── Flashcards ────────────────────────────────────────────────
with tab_flashcards:
    st.markdown("### 🎴 Study Flashcards")
    
    # Initialize session state for flashcards
    if "flashcards" not in st.session_state:
        st.session_state.flashcards = []
    if "current_card_idx" not in st.session_state:
        st.session_state.current_card_idx = 0
    if "show_answer" not in st.session_state:
        st.session_state.show_answer = False
    
    # Load flashcards
    flashcard_dir = Path("data/flashcards")
    
    if not flashcard_dir.exists() or not list(flashcard_dir.glob("*.json")):
        st.info(
            "📚 No flashcards available yet.\n\n"
            "Generate flashcards by running:\n"
            "```\n"
            "python scripts/generate_flashcards.py\n"
            "```"
        )
    else:
        # Flashcard file selector
        flashcard_files = sorted(flashcard_dir.glob("*.json"))
        file_options = ["All Flashcards"] + [f.stem.replace("_flashcards", "") for f in flashcard_files]
        
        selected_file = st.selectbox(
            "Select flashcard set:",
            options=file_options,
            key="flashcard_file_selector"
        )
        
        # Load selected flashcards
        if selected_file == "All Flashcards":
            all_flashcards_path = flashcard_dir / "all_flashcards.json"
            if all_flashcards_path.exists():
                try:
                    import json
                    with open(all_flashcards_path, "r", encoding="utf-8") as f:
                        st.session_state.flashcards = json.load(f)
                except Exception as e:
                    st.error(f"Error loading flashcards: {e}")
                    st.session_state.flashcards = []
            else:
                st.warning("Combined flashcard file not found.")
                st.session_state.flashcards = []
        else:
            selected_path = flashcard_dir / f"{selected_file}_flashcards.json"
            try:
                import json
                with open(selected_path, "r", encoding="utf-8") as f:
                    st.session_state.flashcards = json.load(f)
            except Exception as e:
                st.error(f"Error loading flashcards: {e}")
                st.session_state.flashcards = []
        
        # Display flashcards
        if st.session_state.flashcards:
            total_cards = len(st.session_state.flashcards)
            current_idx = st.session_state.current_card_idx
            current_card = st.session_state.flashcards[current_idx]
            
            # Progress indicator
            st.markdown(
                f'<div class="metric-row">'
                f'<span class="metric-chip">Card {current_idx + 1} of {total_cards}</span>'
                f'</div>',
                unsafe_allow_html=True
            )
            
            st.markdown("---")
            
            # Display question
            st.markdown(
                f'<div class="answer-card">'
                f'<h4>❓ Question</h4>'
                f'{current_card.get("question", "No question")}'
                f'</div>',
                unsafe_allow_html=True
            )
            
            # Show/Hide answer button
            col1, col2, col3 = st.columns([1, 1, 1])
            
            if not st.session_state.show_answer:
                if col2.button("👁 Show Answer", key="show_answer_btn", use_container_width=True):
                    st.session_state.show_answer = True
                    st.rerun()
            else:
                # Display answer
                st.markdown(
                    f'<div class="source-card">'
                    f'<h4>✅ Answer</h4>'
                    f'{current_card.get("answer", "No answer")}'
                    f'</div>',
                    unsafe_allow_html=True
                )
                
                # Optional metadata
                if "topic" in current_card:
                    st.caption(f"📚 Topic: {current_card['topic']}")
                if "lecture_id" in current_card:
                    st.caption(f"🎓 Lecture: {current_card['lecture_id']}")
            
            st.markdown("---")
            
            # Navigation buttons
            nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([1, 1, 1, 1])
            
            # Previous button
            if nav_col1.button("⬅️ Previous", disabled=(current_idx == 0), use_container_width=True):
                st.session_state.current_card_idx = max(0, current_idx - 1)
                st.session_state.show_answer = False
                st.rerun()
            
            # Next button
            if nav_col2.button("➡️ Next", disabled=(current_idx >= total_cards - 1), use_container_width=True):
                st.session_state.current_card_idx = min(total_cards - 1, current_idx + 1)
                st.session_state.show_answer = False
                st.rerun()
            
            # Shuffle button
            if nav_col3.button("🔀 Shuffle", use_container_width=True):
                import random
                random.shuffle(st.session_state.flashcards)
                st.session_state.current_card_idx = 0
                st.session_state.show_answer = False
                st.rerun()
            
            # Reset button
            if nav_col4.button("🔄 Reset", use_container_width=True):
                st.session_state.current_card_idx = 0
                st.session_state.show_answer = False
                st.rerun()
            
            # Keyboard shortcuts info
            st.caption("💡 Tip: Use navigation buttons to browse through flashcards")
        else:
            st.warning("No flashcards loaded. Please select a valid flashcard set.")


# ── History ───────────────────────────────────────────────────
with tab_history:
    st.markdown("### 📜 Query History")
    if not st.session_state.history:
        st.info("No queries yet. Ask a question to see history here.")
    else:
        for i, item in enumerate(reversed(st.session_state.history), 1):
            icon = "🎤" if item["type"] == "audio" else "💬"
            with st.expander(f"{icon} [{i}] {item['query'][:80]}"):
                _display_result(item["result"])
        if st.button("🗑 Clear history"):
            st.session_state.history = []
            st.rerun()
