import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './components/AppShell'
import AboutPage from './pages/AboutPage'
import ChatPage from './pages/ChatPage'
import FlashcardsPage from './pages/FlashcardsPage'
import GraphPage from './pages/GraphPage'
import StatusPage from './pages/StatusPage'
import SummariesPage from './pages/SummariesPage'
import TimelinePage from './pages/TimelinePage'
import VectorSearchPage from './pages/VectorSearchPage'

function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<ChatPage />} />
        <Route path="/timeline" element={<TimelinePage />} />
        <Route path="/graph" element={<GraphPage />} />
        <Route path="/flashcards" element={<FlashcardsPage />} />
        <Route path="/summaries" element={<SummariesPage />} />
        <Route path="/vectors" element={<VectorSearchPage />} />
        <Route path="/status" element={<StatusPage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  )
}

export default App
