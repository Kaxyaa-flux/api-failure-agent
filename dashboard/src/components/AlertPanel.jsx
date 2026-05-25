import { useState } from 'react'
import { Bot, AlertTriangle } from 'lucide-react'

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
  // SQLite datetime('now') returns 'YYYY-MM-DD HH:MM:SS' in UTC without timezone info.
  // We replace space with 'T' and append 'Z' so JS Date parses it correctly as UTC.
  const dateStr = alert.created_at 
    ? (alert.created_at.includes('T') ? alert.created_at : alert.created_at.replace(' ', 'T') + 'Z')
    : null
  const timeStr = dateStr ? new Date(dateStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''

  return (
    <div className={`hero-alert ${alert.severity === 'critical' ? 'critical-pulse' : ''}`}>
      <div className="hero-header">
        🚨 INCIDENT DETECTED
        <span className="hero-time">Anomaly detected at {timeStr}</span>
      </div>
      <div className="hero-meta">
        <span className={severityClass(alert.severity)}>{alert.severity || 'low'}</span>
        <span style={{color: 'var(--text-muted)'}}>Endpoint: {alert.endpoint || 'unknown'}</span>
      </div>

      <div className="hero-section">
        <div className="hero-section-title">Root Cause</div>
        <div className="hero-divider">──────────</div>
        <div className="hero-text">{alert.root_cause || alert.issue || 'Unknown root cause detected.'}</div>
      </div>

      {alert.impact && (
        <div className="hero-section">
          <div className="hero-section-title">Impact</div>
          <div className="hero-divider">──────</div>
          <div className="hero-text">{alert.impact}</div>
        </div>
      )}

      {Array.isArray(alert.steps) && alert.steps.length > 0 && (
        <div className="hero-section" style={{marginBottom: 0}}>
          <div className="hero-section-title">Recommended Actions</div>
          <div className="hero-divider">───────────────────</div>
          <div className="hero-text">
            {alert.steps.map((step, i) => (
              <div key={i}>{i + 1}. {step}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function AlertPanel({ alerts = [], expanded, health }) {
  const visible = expanded ? alerts : alerts.slice(0, 8)

  return (
    <>
      <div className="section-header">
        <div className="section-title">
          <Bot size={16} style={{ color: 'var(--purple)' }} />
          AI Alerts
          <span className="section-badge">{alerts.length}</span>
        </div>
        {health === true && (
          <div className="poll-indicator">
            <span className="poll-dot" /> Live
          </div>
        )}
      </div>

      {alerts.length === 0 && (
        <div className="empty">
          <Bot size={32} />
          <span>No alerts yet — click <strong>Seed Data</strong> to generate some</span>
        </div>
      )}

      {alerts.length > 0 && (
        <div className="scroll-list">
          {visible.map((alert, i) => (
            <AlertCard key={alert.db_id ?? i} alert={alert} />
          ))}
        </div>
      )}
    </>
  )
}
