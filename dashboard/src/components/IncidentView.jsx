import { Shield, AlertTriangle, Clock } from 'lucide-react'

function scBadge(sc) {
  if (sc >= 500) return <span className="sc sc-5xx">{sc}</span>
  if (sc >= 400) return <span className="sc sc-4xx">{sc}</span>
  if (sc >= 300) return <span className="sc sc-3xx">{sc}</span>
  return <span className="sc sc-2xx">{sc}</span>
}

function fmtTime(ts) {
  try { return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }
  catch { return ts }
}

/**
 * IncidentView receives pre-fetched `clusters` from App.jsx via the /clusters API.
 * No internal polling or client-side grouping — backend cluster data is used directly.
 * Only clusters with status_code >= 400 are shown as active incidents.
 */
export default function IncidentView({ clusters = [] }) {
  // Filter to error clusters only, already sorted by count desc from backend
  const incidents = clusters.filter(c => c.status_code >= 400)

  return (
    <>
      <div className="section-header">
        <div className="section-title">
          <Shield size={16} style={{ color: 'var(--red)' }} />
          Active Incidents
          <span className="section-badge">{incidents.length}</span>
        </div>
        <div className="poll-indicator">
          <span className="poll-dot" /> Live · 2s
        </div>
      </div>

      {incidents.length === 0 && (
        <div className="empty">
          <Shield size={32} />
          <span>No incidents detected — all endpoints healthy</span>
        </div>
      )}

      <div className="scroll-list">
        {incidents.map((inc, i) => (
          <div key={`${inc.endpoint}-${inc.status_code}-${i}`} className="incident-card">
            <div className="incident-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <AlertTriangle size={14} style={{ color: 'var(--red)', flexShrink: 0 }} />
                <span className="incident-ep">{inc.endpoint}</span>
              </div>
              <span className="incident-count">{inc.count} errors</span>
            </div>

            <div className="incident-codes">
              {scBadge(inc.status_code)}
              <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 6 }}>
                {inc.error_class}
              </span>
            </div>

            {inc.methods?.length > 0 && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                Methods: {inc.methods.join(', ')}
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
              <Clock size={11} />
              Incident active for {Math.max(1, Math.round((new Date(inc.last_seen) - new Date(inc.first_seen)) / 60000))} min ({fmtTime(inc.first_seen)} → {fmtTime(inc.last_seen)})
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
