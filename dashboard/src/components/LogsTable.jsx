import { useState, useEffect, useCallback } from 'react'
import { Database, RefreshCw } from 'lucide-react'

const POLL_MS = 5000

function methodBadge(m) {
  const cls = `method method-${m?.toUpperCase()}` 
  return <span className={cls}>{m}</span>
}

function statusBadge(sc) {
  if (sc >= 500) return <span className="sc sc-5xx">{sc}</span>
  if (sc >= 400) return <span className="sc sc-4xx">{sc}</span>
  if (sc >= 300) return <span className="sc sc-3xx">{sc}</span>
  return <span className="sc sc-2xx">{sc}</span>
}

function fmtTime(ts) {
  try {
    return new Date(ts).toLocaleTimeString([], {
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    })
  } catch { return ts }
}

export default function LogsTable() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)

  const poll = useCallback(async () => {
    try {
      const res = await fetch('/logs')
      const data = await res.json()
      // Show latest 10 (data already newest-first from API)
      setLogs(data.slice(0, 10))
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    poll()
    const id = setInterval(poll, POLL_MS)
    return () => clearInterval(id)
  }, [poll])

  return (
    <>
      <div className="section-header">
        <div className="section-title">
          <Database size={16} style={{ color: 'var(--teal)' }} />
          Live Logs
          <span className="section-badge">latest 10</span>
        </div>
        <div className="poll-indicator">
          {loading
            ? <><RefreshCw size={10} className="spin" /> Loading</>
            : <><span className="poll-dot" /> Live · 5s</>
          }
        </div>
      </div>

      {!loading && logs.length === 0 && (
        <div className="empty">
          <Database size={32} />
          <span>No logs yet — send requests or click Seed Data</span>
        </div>
      )}

      {logs.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Method</th>
                <th>Endpoint</th>
                <th>Status</th>
                <th>Latency</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log, i) => {
                const isError   = log.status_code >= 400
                const isSlowLat = log.latency > 1000
                return (
                  <tr key={log.id ?? i} className={isError ? 'row-error' : ''}>
                    <td style={{ color: 'var(--text-muted)', fontFamily: 'monospace', fontSize: 12 }}>
                      {fmtTime(log.timestamp)}
                    </td>
                    <td>{methodBadge(log.method)}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{log.endpoint}</td>
                    <td>{statusBadge(log.status_code)}</td>
                    <td className={isSlowLat ? 'latency-warn' : ''}>
                      {log.latency?.toFixed(1)} ms
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
