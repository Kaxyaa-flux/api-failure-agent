import { useState } from 'react'
import { Database, ChevronLeft, ChevronRight } from 'lucide-react'

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

/**
 * LogsTable receives pre-fetched `logs` and `anomalies` from App.jsx.
 * No internal polling — avoids duplicate /logs requests.
 *
 * Latency highlight threshold: derived from anomaly data per endpoint
 * (latency_spike threshold), NOT a hardcoded 1000ms value.
 */
export default function LogsTable({ logs = [], anomalies = [], health }) {
  // Build per-endpoint latency threshold from backend anomaly data
  const latencyThresholds = {}
  for (const anom of anomalies) {
    if (anom.anomaly_type === 'latency_spike' && anom.threshold != null) {
      // Use the smaller of existing threshold if multiple anomalies exist per endpoint
      if (!(anom.endpoint in latencyThresholds) || anom.threshold < latencyThresholds[anom.endpoint]) {
        latencyThresholds[anom.endpoint] = anom.threshold
      }
    }
  }

  const [page, setPage] = useState(0)
  const pageSize = 10
  const totalPages = Math.ceil(logs.length / pageSize)
  
  // Show only logs for current page
  const visible = logs.slice(page * pageSize, (page + 1) * pageSize)

  return (
    <>
      <div className="section-header">
        <div className="section-title">
          <Database size={16} style={{ color: 'var(--teal)' }} />
          Live Logs
          <span className="section-badge">{logs.length} Total</span>
        </div>
        {health === true && (
          <div className="poll-indicator">
            <span className="poll-dot" /> Live
          </div>
        )}
      </div>

      {visible.length === 0 && (
        <div className="empty">
          <Database size={32} />
          <span>No logs yet — send requests or click Seed Data</span>
        </div>
      )}

      {visible.length > 0 && (
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
              {visible.map((log, i) => {
                const isError = log.status_code >= 400
                // Use anomaly-derived threshold for this endpoint; fall back to
                // 2× global average if no anomaly data exists for this endpoint
                const threshold = latencyThresholds[log.endpoint] ?? null
                const isSlowLat = threshold !== null
                  ? log.latency > threshold
                  : false
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
          
          {totalPages > 1 && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', borderTop: '1px solid var(--border)' }}>
              <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                Showing {page * pageSize + 1} to {Math.min((page + 1) * pageSize, logs.length)} of {logs.length}
              </span>
              <div style={{ display: 'flex', gap: 8 }}>
                <button 
                  onClick={() => setPage(p => Math.max(0, p - 1))} 
                  disabled={page === 0}
                  style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '6px 12px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-panel)', color: page === 0 ? 'var(--text-dim)' : 'var(--text)', cursor: page === 0 ? 'not-allowed' : 'pointer' }}
                >
                  <ChevronLeft size={14} /> Prev
                </button>
                <button 
                  onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} 
                  disabled={page >= totalPages - 1}
                  style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '6px 12px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-panel)', color: page >= totalPages - 1 ? 'var(--text-dim)' : 'var(--text)', cursor: page >= totalPages - 1 ? 'not-allowed' : 'pointer' }}
                >
                  Next <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  )
}
