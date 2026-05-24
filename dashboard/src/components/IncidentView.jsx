import { useState, useEffect, useCallback } from 'react'
import { Shield, AlertTriangle, RefreshCw, Clock } from 'lucide-react'

const POLL_MS = 5000

function scBadge(sc) {
  if (sc >= 500) return <span className="sc sc-5xx">{sc}</span>
  if (sc >= 400) return <span className="sc sc-4xx">{sc}</span>
  if (sc >= 300) return <span className="sc sc-3xx">{sc}</span>
  return <span className="sc sc-2xx">{sc}</span>
}

export default function IncidentView() {
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(true)

  const poll = useCallback(async () => {
    try {
      const res = await fetch('/logs')
      const logs = await res.json()

      // Group errors (status >= 400) by endpoint client-side
      const byEndpoint = {}
      for (const log of logs) {
        if (log.status_code < 400) continue
        const ep = log.endpoint
        if (!byEndpoint[ep]) {
          byEndpoint[ep] = {
            endpoint: ep,
            count: 0,
            statusCodes: new Set(),
            timestamps: [],
          }
        }
        byEndpoint[ep].count++
        byEndpoint[ep].statusCodes.add(log.status_code)
        byEndpoint[ep].timestamps.push(log.timestamp)
      }

      // Convert to sorted array (highest error count first)
      const list = Object.values(byEndpoint).sort((a, b) => b.count - a.count)

      // Compute time window for each incident
      const result = list.map(inc => {
        const sorted = [...inc.timestamps].sort()
        const first = sorted[0]
        const last  = sorted[sorted.length - 1]
        return {
          endpoint: inc.endpoint,
          count: inc.count,
          statusCodes: [...inc.statusCodes].sort(),
          first_seen: first,
          last_seen: last,
        }
      })

      setIncidents(result)
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    poll()
    const id = setInterval(poll, POLL_MS)
    return () => clearInterval(id)
  }, [poll])

  function fmtTime(ts) {
    try { return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }
    catch { return ts }
  }

  return (
    <>
      <div className="section-header">
        <div className="section-title">
          <Shield size={16} style={{ color: 'var(--red)' }} />
          Active Incidents
          <span className="section-badge">{incidents.length}</span>
        </div>
        <div className="poll-indicator">
          {loading
            ? <><RefreshCw size={10} className="spin" /> Loading</>
            : <><span className="poll-dot" /> Live · 5s</>
          }
        </div>
      </div>

      {!loading && incidents.length === 0 && (
        <div className="empty">
          <Shield size={32} />
          <span>No incidents detected — all endpoints healthy</span>
        </div>
      )}

      <div className="scroll-list">
        {incidents.map(inc => (
          <div key={inc.endpoint} className="incident-card">
            <div className="incident-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <AlertTriangle size={14} style={{ color: 'var(--red)', flexShrink: 0 }} />
                <span className="incident-ep">{inc.endpoint}</span>
              </div>
              <span className="incident-count">{inc.count} errors</span>
            </div>

            <div className="incident-codes">
              {inc.statusCodes.map(sc => (
                <span key={sc}>{scBadge(sc)}</span>
              ))}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
              <Clock size={11} />
              {fmtTime(inc.first_seen)} → {fmtTime(inc.last_seen)}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
