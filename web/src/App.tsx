import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import DecisionDay from './pages/DecisionDay'
import Accuracy from './pages/Accuracy'
import { useMeta } from './api/client'

export default function App() {
  const meta = useMeta()
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" />
          <div>
            <div className="brand-title">Wind Day-Ahead Desk</div>
            <div className="brand-sub">GB national wind · Elexon FUELHH + WINDFOR · January 2026</div>
          </div>
        </div>
        <nav>
          <NavLink to="/decision">Decision day</NavLink>
          <NavLink to="/accuracy">Forecast accuracy</NavLink>
          <a href="/api/docs" target="_blank" rel="noreferrer">
            API
          </a>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/decision" replace />} />
          <Route path="/decision" element={<DecisionDay />} />
          <Route path="/accuracy" element={<Accuracy />} />
        </Routes>
      </main>
      <footer className="foot">
        {meta.data ? (
          <>
            <span>{meta.data.assumptions.decision_window}</span>
            <span>Snapshot fetched {meta.data.snapshot.fetched_at?.slice(0, 10)} from Elexon Insights.</span>
          </>
        ) : null}
      </footer>
    </div>
  )
}
