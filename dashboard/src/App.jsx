import { useState, useEffect, useCallback } from 'react'
import {
  AlertTriangle, CheckCircle, Zap, TrendingUp, Activity,
  RefreshCw, Database, Shield, ChevronRight, Bot, Cpu,
} from 'lucide-react'
import AlertPanel from './components/AlertPanel'
import LatencyChart from './components/LatencyChart'
import IncidentView from './components/IncidentView'
import LogsTable from './components/LogsTable'

const POLL_MS = 5000

export default function App() {
  const [health, setHealth] = useState(null)
  const [stats, setStats] = useState({ logs: 0, alerts: 0, anomalies: 0 })
  const [seeding, setSeeding] = useState(false)
  const [seedMsg, setSeedMsg] = useState('')
  const [activeTab, setActiveTab] = useState('dashboard')

  const fetchStats = useCallback(async () => {
    try {
      const [logsRes, alertsRes, anomRes] = await Promise.all([
        fetch('/logs'),
        fetch('/alerts'),
        fetch('/anomalies'),
      ])
      const [logs, alerts, anomalies] = await Promise.all([
        logsRes.json(), alertsRes.json(), anomRes.json(),
      ])
      setStats({ logs: logs.length, alerts: alerts.length, anomalies: anomalies.length })
    } catch { /* silent */ }
  }, [])

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch('/health')
      const data = await res.json()
      setHealth(data.status === 'ok')
    } catch {
      setHealth(false)
    }
  }, [])

  const handleSeed = async () => {
    setSeeding(true)
    setSeedMsg('')
    try {
      const res = await fetch('/seed', { method: 'POST' })
      const data = await res.json()
      setSeedMsg(`✓ Seeded ${data.logs_seeded} logs — ${data.anomalies_found} anomaly(ies) detected`)
      fetchStats()
    } catch {
      setSeedMsg('✗ Seed failed — is the backend running?')
    } finally {
      setSeeding(false)
    }
  }

  useEffect(() => {
    fetchHealth()
    fetchStats()
    const id = setInterval(() => { fetchHealth(); fetchStats() }, POLL_MS)
    return () => clearInterval(id)
  }, [fetchHealth, fetchStats])

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
          <div className={`status-pill ${health === true ? 'online' : health === false ? 'offline' : 'unknown'}`}>
            {health === true ? <CheckCircle size={12} /> : <AlertTriangle size={12} />}
            {health === true ? 'Backend Online' : health === false ? 'Backend Offline' : 'Connecting…'}
          </div>
          <button className="seed-btn" onClick={handleSeed} disabled={seeding}>
            {seeding ? <RefreshCw size={14} className="spin" /> : <Zap size={14} />}
            {seeding ? 'Seeding…' : 'Seed Data'}
          </button>
        </div>
      </header>

      {seedMsg && (
        <div className={`seed-toast ${seedMsg.startsWith('✓') ? 'success' : 'error'}`}>
          {seedMsg}
        </div>
      )}

      {/* ── Stat Cards ──────────────────────────────────────────────── */}
      <div className="stats-row">
        {[
          { label: 'Total Logs', value: stats.logs, icon: Database, color: 'blue' },
          { label: 'Anomalies', value: stats.anomalies, icon: TrendingUp, color: 'orange' },
          { label: 'AI Alerts', value: stats.alerts, icon: AlertTriangle, color: 'red' },
        ].map(s => (
          <div key={s.label} className={`stat-card stat-${s.color}`}>
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
            <section className="card wide"><LatencyChart /></section>
            <section className="card"><AlertPanel /></section>
          </>
        )}
        {activeTab === 'alerts' && (
          <section className="card span-full"><AlertPanel expanded /></section>
        )}
        {activeTab === 'incidents' && (
          <section className="card span-full"><IncidentView /></section>
        )}
        {activeTab === 'logs' && (
          <section className="card span-full"><LogsTable /></section>
        )}
      </main>
    </div>
  )
}
