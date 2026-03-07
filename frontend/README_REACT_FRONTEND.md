# AI Lecture Intelligence — React Frontend

Modern AI dashboard frontend replacing the previous Streamlit UI.

## Stack
- React + Vite
- TailwindCSS
- Framer Motion
- React Query
- Recharts
- D3.js

## Pages
- AI Chat Assistant
- Lecture Timeline
- Concept Knowledge Graph
- Flashcard Study Mode
- Lecture Summaries
- Vector Search Visualization
- System Status
- About Project

## Setup
1. Copy environment file:
   - `cp .env.example .env`
2. Set API URL in `.env`:
   - `VITE_API_BASE_URL=http://localhost:8000`
3. Install dependencies:
   - `npm install`
4. Start dev server:
   - `npm run dev`

## Backend
Run the FastAPI backend from project root:
- `uvicorn backend.app.main:app --reload --port 8000`

## Notes
- Default theme is dark.
- UI uses glassmorphism cards and motion transitions.
- `/flashcards` and `/summaries` include fallback demo data if those endpoints are unavailable.
