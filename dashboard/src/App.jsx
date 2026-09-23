import { useState, useEffect, useCallback } from 'react'
import {
  AlertTriangle, CheckCircle, TrendingUp, Activity,
  Database, Shield, ChevronRight, Bot, Cpu, Sun, Moon,
} from 'lucide-react'
import AlertPanel from './components/AlertPanel'
import LatencyChart from './components/LatencyChart'
import IncidentView from './components/IncidentView'
import LogsTable from './components/LogsTable'

const POLL_MS = 5000

export default function App() {
  const [health, setHealth] = useState(null)
  const [stats, setStats] = useState({ logs: 0, alerts: 0, anomalies: 0 })
  const [activeTab, setActiveTab] = useState('dashboard')
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'light')

  useEffect(() => {
    document.documentElement.className = theme === 'dark' ? 'dark' : ''
    localStorage.setItem('theme', theme)
  }, [theme])

  // Shared data fetched centrally to avoid per-component duplicate polling
  const [logs, setLogs] = useState([])
  const [anomalies, setAnomalies] = useState([])
  const [clusters, setClusters] = useState([])
  const [alerts, setAlerts] = useState([])

  const fetchAll = useCallback(async () => {
    try {
      const res = await fetch('/status')

      // Validate response before parsing
      if (!res.ok) {
        console.warn('[App] fetch status response was not ok')
        return
      }

      const data = await res.json()

      setLogs(data.logs)
      setAlerts(data.alerts)
      setAnomalies(data.anomalies)
      setClusters(data.clusters)
      setStats({ logs: data.logs.length, alerts: data.alerts.length, anomalies: data.anomalies.length })
    } catch (err) {
      console.warn('[App] fetchAll error:', err)
    }
  }, [])

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch('/health')
      if (!res.ok) { setHealth(false); return }
      const data = await res.json()
      setHealth(data.status === 'ok')
    } catch {
      setHealth(false)
    }
  }, [])

  useEffect(() => {
    fetchHealth()
    fetchAll()
    const id = setInterval(() => { fetchHealth(); fetchAll() }, POLL_MS)
    return () => clearInterval(id)
  }, [fetchHealth, fetchAll])

  const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: Activity },
    { id: 'alerts', label: 'AI Alerts', icon: Bot },
    { id: 'incidents', label: 'Incidents', icon: Shield },
    { id: 'logs', label: 'Live Logs', icon: Database },
  ]

  return (
    <div className="app">
      {/* ── Header ──────────────────────────────────────────────────── */}
      <header className="header">
        <div className="header-brand">
          <div className="brand-icon"><Cpu size={20} /></div>
          <div>
            <h1 className="brand-title">API Failure Agent</h1>
            <p className="brand-sub">AI-Powered Detection &amp; Diagnostics</p>
          </div>
        </div>

        <nav className="header-nav">
          {tabs.map(t => (
            <button
              key={t.id}
              className={`nav-btn ${activeTab === t.id ? 'active' : ''}`}
              onClick={() => setActiveTab(t.id)}
            >
              <t.icon size={14} />
              {t.label}
            </button>
          ))}
        </nav>

        <div className="header-actions">
          <button 
            className="theme-btn" 
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            title="Toggle theme"
          >
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          </button>
          
          <div className={`status-pill ${health === true ? 'online' : health === false ? 'offline' : 'unknown'}`}>
            {health === true ? <CheckCircle size={12} /> : <AlertTriangle size={12} />}
            {health === true ? 'Backend Online' : health === false ? 'Backend Offline' : 'Connecting…'}
          </div>
        </div>
      </header>

      {/* ── Stat Cards ──────────────────────────────────────────────── */}
      <div className="stats-row">
        {[
          { label: 'Total Logs', value: stats.logs, icon: Database, color: 'blue', tab: 'logs' },
          { label: 'Anomalies', value: stats.anomalies, icon: TrendingUp, color: 'orange', tab: 'incidents' },
          { label: 'AI Alerts', value: stats.alerts, icon: AlertTriangle, color: 'red', tab: 'alerts' },
        ].map(s => (
          <div 
            key={s.label} 
            className={`stat-card stat-${s.color}`}
            onClick={() => setActiveTab(s.tab)}
            style={{ cursor: 'pointer' }}
          >
            <div className="stat-icon"><s.icon size={20} /></div>
            <div>
              <div className="stat-value">{s.value}</div>
              <div className="stat-label">{s.label}</div>
            </div>
            <ChevronRight size={16} className="stat-arrow" />
          </div>
        ))}
      </div>

      {/* ── Main Content ────────────────────────────────────────────── */}
      <main className="main-grid">
        {activeTab === 'dashboard' && (
          <>
            <section className="card wide">
              <LatencyChart logs={logs} anomalies={anomalies} health={health} />
            </section>
            <section className="card">
              <AlertPanel alerts={alerts} health={health} />
            </section>
          </>
        )}
        {activeTab === 'alerts' && (
          <section className="card span-full">
            <AlertPanel alerts={alerts} expanded health={health} />
          </section>
        )}
        {activeTab === 'incidents' && (
          <section className="card span-full">
            <IncidentView clusters={clusters} health={health} />
          </section>
        )}
        {activeTab === 'logs' && (
          <section className="card span-full">
            <LogsTable logs={logs} anomalies={anomalies} health={health} />
          </section>
        )}
      </main>
    </div>
  )
}
