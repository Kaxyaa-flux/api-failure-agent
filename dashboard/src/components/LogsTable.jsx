import React, { useState, useEffect } from 'react';
import { Server, Clock, Activity, Hash, AlertTriangle } from 'lucide-react';

const LogsTable = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const response = await fetch('http://localhost:8000/logs');
        if (!response.ok) throw new Error('Failed to fetch logs');
        const data = await response.json();
        setLogs(data.slice(0, 10)); // Show latest 10 logs
        setError(null);
      } catch (err) {
        setError('Unable to connect to backend.');
      } finally {
        setLoading(false);
      }
    };

    fetchLogs();
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading && logs.length === 0) return <div className="loading">Loading logs...</div>;

  return (
    <div className="component-container">
      <h2 className="panel-title"><Server size={20} className="icon-blue" /> Live API Logs</h2>
      
      {error && <div className="error-banner">{error}</div>}
      
      <div className="table-responsive">
        <table className="data-table">
          <thead>
            <tr>
              <th><div className="th-content"><Clock size={16} /> Timestamp</div></th>
              <th><div className="th-content"><Activity size={16} /> Method</div></th>
              <th>Endpoint</th>
              <th><div className="th-content"><Hash size={16} /> Status</div></th>
              <th>Latency (ms)</th>
            </tr>
          </thead>
          <tbody>
            {logs.length > 0 ? (
              logs.map((log, index) => (
                <tr key={index} className={log.status_code >= 400 ? 'error-row' : ''}>
                  <td>{new Date(log.timestamp).toLocaleTimeString()}</td>
                  <td>
                    <span className={`method-badge ${log.method.toLowerCase()}`}>
                      {log.method}
                    </span>
                  </td>
                  <td className="endpoint-cell">{log.endpoint}</td>
                  <td>
                    <span className={`status-badge status-${log.status_code >= 500 ? '5xx' : log.status_code >= 400 ? '4xx' : '2xx'}`}>
                      {log.status_code}
                    </span>
                  </td>
                  <td>
                    <span className={log.latency > 1000 ? 'high-latency' : ''}>
                      {parseFloat(log.latency).toFixed(2)}
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="5" className="empty-state">No logs available</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      
      <style>{`
        .component-container { height: 100%; display: flex; flex-direction: column; }
        .icon-blue { color: var(--accent-color); }
        .error-banner { background: rgba(239, 68, 68, 0.1); color: var(--danger-color); padding: 0.75rem; border-radius: 6px; margin-bottom: 1rem; font-size: 0.875rem; border: 1px solid rgba(239, 68, 68, 0.2); }
        .table-responsive { overflow-x: auto; }
        .data-table { width: 100%; border-collapse: collapse; text-align: left; font-size: 0.875rem; }
        .data-table th { padding: 0.75rem 1rem; border-bottom: 1px solid var(--border-color); color: var(--text-secondary); font-weight: 500; }
        .th-content { display: flex; align-items: center; gap: 0.375rem; }
        .data-table td { padding: 0.875rem 1rem; border-bottom: 1px solid var(--border-color); color: var(--text-primary); }
        .data-table tr:hover td { background: rgba(255, 255, 255, 0.02); }
        .error-row { background: rgba(239, 68, 68, 0.05); }
        
        .method-badge { padding: 0.125rem 0.375rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }
        .method-badge.get { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
        .method-badge.post { background: rgba(16, 185, 129, 0.15); color: #34d399; }
        .method-badge.put { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
        .method-badge.delete { background: rgba(239, 68, 68, 0.15); color: #f87171; }
        
        .endpoint-cell { font-family: monospace; color: #d1d5db; }
        
        .status-badge { padding: 0.125rem 0.5rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
        .status-2xx { background: rgba(16, 185, 129, 0.15); color: #34d399; }
        .status-4xx { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
        .status-5xx { background: rgba(239, 68, 68, 0.15); color: #f87171; }
        
        .high-latency { color: var(--warning-color); font-weight: 500; }
        .empty-state { text-align: center; color: var(--text-secondary); padding: 2rem !important; }
      `}</style>
    </div>
  );
};

export default LogsTable;
