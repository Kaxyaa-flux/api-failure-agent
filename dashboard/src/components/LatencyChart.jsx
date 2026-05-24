import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts'
import { Activity } from 'lucide-react'

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const p = payload[0]?.payload
  return (
    <div style={{
      background: '#1a2035', border: '1px solid rgba(255,255,255,.1)',
      borderRadius: 8, padding: '10px 14px', fontSize: 12,
    }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
      <div style={{ color: p?.isAnomaly ? 'var(--red)' : 'var(--blue)', fontWeight: 600 }}>
        {p?.latency?.toFixed(0)} ms
      </div>
      <div style={{ color: 'var(--text-muted)', marginTop: 4 }}>{p?.endpoint}</div>
      <div>Status: <span style={{ color: p?.status_code >= 400 ? 'var(--red)' : 'var(--green)' }}>
        {p?.status_code}
      </span></div>
      {p?.isAnomaly && (
        <div style={{ color: 'var(--red)', marginTop: 4, fontWeight: 600 }}>⚠ Anomaly</div>
      )}
    </div>
  )
}

function CustomDot({ cx, cy, payload }) {
  if (!payload?.isAnomaly) return null
  return (
    <g>
      <circle cx={cx} cy={cy} r={7} fill="var(--red)" opacity={0.3} />
      <circle cx={cx} cy={cy} r={4} fill="var(--red)" stroke="#fff" strokeWidth={1.5} />
    </g>
  )
}

/**
 * LatencyChart receives pre-fetched `logs` and `anomalies` from App.jsx.
 * No internal polling — avoids duplicate /logs and /anomalies requests.
 */
export default function LatencyChart({ logs = [], anomalies = [] }) {
  // Build a map: endpoint → threshold value from anomaly data
  // Only mark a log point as anomalous if its latency exceeds the
  // per-endpoint threshold (latency_spike anomalies only).
  const endpointThresholds = {}
  for (const anom of anomalies) {
    if (anom.anomaly_type === 'latency_spike') {
      endpointThresholds[anom.endpoint] = anom.threshold ?? 0
    }
  }

  // Take the 30 most-recent logs (newest-first from API → reverse for chart)
  const slice = logs.slice(0, 30).reverse()

  const chartData = slice.map(log => {
    const threshold = endpointThresholds[log.endpoint]
    // A point is an anomaly only if this endpoint has a latency_spike AND
    // this specific log's latency exceeds that endpoint's spike threshold.
    const isAnomaly = threshold !== undefined && log.latency > threshold
    return {
      label: new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      latency: log.latency,
      endpoint: log.endpoint,
      status_code: log.status_code,
      isAnomaly,
    }
  })

  const avgLatency = chartData.length
    ? Math.round(chartData.reduce((s, p) => s + p.latency, 0) / chartData.length)
    : 0

  return (
    <>
      <div className="section-header">
        <div className="section-title">
          <Activity size={16} style={{ color: 'var(--blue)' }} />
          Latency Monitor
          {avgLatency > 0 && (
            <span className="section-badge">avg {avgLatency}ms</span>
          )}
        </div>
        <div className="poll-indicator">
          <span className="poll-dot" /> Live · 5s
        </div>
      </div>

      {chartData.length === 0 && (
        <div className="empty" style={{ height: 240 }}>
          <Activity size={32} />
          <span>No log data yet — click Seed Data</span>
        </div>
      )}

      {chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData} margin={{ top: 8, right: 16, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.05)" />
            <XAxis
              dataKey="label"
              tick={{ fill: '#6b7280', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fill: '#6b7280', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={v => `${v}ms`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: 12, color: '#6b7280', paddingTop: 8 }}
              formatter={v => v === 'latency' ? 'Latency (ms) — all endpoints' : v}
            />
            {avgLatency > 0 && (
              <ReferenceLine
                y={avgLatency * 2}
                stroke="rgba(239,68,68,.5)"
                strokeDasharray="4 3"
                label={{ value: '2× avg', fill: '#ef4444', fontSize: 10, position: 'right' }}
              />
            )}
            <Line
              type="monotone"
              dataKey="latency"
              stroke="var(--blue)"
              strokeWidth={2}
              dot={<CustomDot />}
              activeDot={{ r: 5, fill: 'var(--blue)' }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </>
  )
}
