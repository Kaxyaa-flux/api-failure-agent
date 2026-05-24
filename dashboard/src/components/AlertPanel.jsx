import { useState, useEffect, useCallback } from 'react'
import { Bot, AlertTriangle, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react'

const POLL_MS = 5000

function severityClass(s) {
  if (s === 'critical') return 'sev sev-critical'
  if (s === 'high')     return 'sev sev-high'
  if (s === 'medium')   return 'sev sev-medium'
  return 'sev sev-low'
}

function SeverityIcon({ severity }) {
  const size = 14
  if (severity === 'critical' || severity === 'high')
    return <AlertTriangle size={size} style={{ color: 'var(--red)' }} />
  if (severity === 'medium')
    return <AlertTriangle size={size} style={{ color: 'var(--yellow)' }} />
  return <AlertTriangle size={size} style={{ color: 'var(--green)' }} />
}

function AlertCard({ alert }) {
  const [open, setOpen] = useState(false)
  const confidence = typeof alert.confidence === 'number' ? alert.confidence : 0
  const pct = Math.round(confidence * 100)

  return (
    <div className="alert-card">
      <div className="alert-header">
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
          <SeverityIcon severity={alert.severity} />
          <div>
            <div className="alert-title">{alert.issue || 'Unknown issue'}</div>
            {alert.endpoint && (
              <div style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                {alert.endpoint}
              </div>
            )}
          </div>
        </div>
        <div className="alert-badges">
          <span className={severityClass(alert.severity)}>{alert.severity || 'low'}</span>
          <span className={`source-badge source-${alert.source || 'mock'}`}>
            {alert.source || 'mock'}
          </span>
        </div>
      </div>

      {/* Confidence bar */}
      <div className="confidence-row" style={{ marginBottom: 8 }}>
        <span>Confidence</span>
        <div className="progress-wrap" style={{ flex: 1 }}>
          <div className="progress-fill" style={{ width: `${pct}%` }} />
        </div>
        <span style={{ fontWeight: 600, color: 'var(--text)' }}>{pct}%</span>
      </div>

      {/* Root cause */}
      {alert.root_cause && (
        <div className="alert-cause">
          <strong style={{ color: 'var(--text-muted)', fontSize: 11 }}>ROOT CAUSE</strong>
          <div style={{ marginTop: 4 }}>{alert.root_cause}</div>
        </div>
      )}

      {/* Steps (collapsible) */}
      {Array.isArray(alert.steps) && alert.steps.length > 0 && (
        <>
          <button
            onClick={() => setOpen(o => !o)}
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--text-muted)', fontSize: 12, padding: '2px 0',
            }}
          >
            {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            {open ? 'Hide' : 'Show'} remediation steps ({alert.steps.length})
          </button>
          {open && (
            <ul className="alert-steps" style={{ marginTop: 8 }}>
              {alert.steps.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}

export default function AlertPanel({ expanded }) {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)

  const poll = useCallback(async () => {
    try {
      const res = await fetch('/alerts')
      const data = await res.json()
      // Sort by confidence descending — NO timestamp field
      data.sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0))
      setAlerts(data)
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    poll()
    const id = setInterval(poll, POLL_MS)
    return () => clearInterval(id)
  }, [poll])

  const visible = expanded ? alerts : alerts.slice(0, 8)

  return (
    <>
      <div className="section-header">
        <div className="section-title">
          <Bot size={16} style={{ color: 'var(--purple)' }} />
          AI Alerts
          <span className="section-badge">{alerts.length}</span>
        </div>
        <div className="poll-indicator">
          <span className="poll-dot" />
          Live · 5s
        </div>
      </div>

      {loading && (
        <div className="empty">
          <RefreshCw size={24} className="spin" />
          <span>Loading alerts…</span>
        </div>
      )}

      {!loading && alerts.length === 0 && (
        <div className="empty">
          <Bot size={32} />
          <span>No alerts yet — click <strong>Seed Data</strong> to generate some</span>
        </div>
      )}

      {!loading && alerts.length > 0 && (
        <div className="scroll-list">
          {visible.map((alert, i) => (
            <AlertCard key={alert.db_id ?? i} alert={alert} />
          ))}
        </div>
      )}
    </>
  )
}
