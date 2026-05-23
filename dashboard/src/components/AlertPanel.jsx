import React, { useState, useEffect } from 'react';
import { AlertTriangle, AlertCircle, Info, ChevronRight } from 'lucide-react';

const AlertPanel = () => {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const response = await fetch('http://localhost:8000/alerts');
        if (!response.ok) throw new Error('Failed to fetch alerts');
        const data = await response.json();
        
        // Ensure newest alerts are on top
        const sortedAlerts = data.sort((a, b) => new Date(b.timestamp || 0) - new Date(a.timestamp || 0));
        setAlerts(sortedAlerts);
      } catch (err) {
        console.error("Error fetching alerts", err);
      } finally {
        setLoading(false);
      }
    };

    fetchAlerts();
    const interval = setInterval(fetchAlerts, 5000);
    return () => clearInterval(interval);
  }, []);

  const getSeverityIcon = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'high':
      case 'critical':
        return <AlertTriangle size={18} className="severity-icon critical" />;
      case 'medium':
      case 'warning':
        return <AlertCircle size={18} className="severity-icon warning" />;
      default:
        return <Info size={18} className="severity-icon info" />;
    }
  };

  return (
    <div className="component-container">
      <h2 className="panel-title">
        <AlertTriangle size={20} className="icon-orange" /> 
        AI Diagnostics & Alerts
        {alerts.length > 0 && <span className="alert-count">{alerts.length}</span>}
      </h2>
      
      <div className="alerts-list">
        {loading && alerts.length === 0 ? (
          <div className="loading">Analyzing system state...</div>
        ) : alerts.length === 0 ? (
          <div className="empty-state">
            <div className="all-clear-icon">✓</div>
            <p>System is healthy. No AI alerts generated.</p>
          </div>
        ) : (
          alerts.map((alert, index) => (
            <div key={index} className={`alert-card severity-${alert.severity?.toLowerCase() || 'low'}`}>
              <div className="alert-header">
                <div className="alert-title">
                  {getSeverityIcon(alert.severity)}
                  <h3>{alert.issue || 'Unknown Issue'}</h3>
                </div>
                <span className="alert-time">
                  {alert.timestamp ? new Date(alert.timestamp).toLocaleTimeString() : 'Just now'}
                </span>
              </div>
              
              <div className="alert-body">
                <div className="alert-section">
                  <span className="section-label">Root Cause</span>
                  <p>{alert.root_cause || alert.rootCause || 'AI is still analyzing the root cause...'}</p>
                </div>
                
                {(alert.steps || alert.debugging_steps || alert.debuggingSteps) && (
                  <div className="alert-section">
                    <span className="section-label">Suggested Fix</span>
                    <ul className="steps-list">
                      {(alert.steps || alert.debugging_steps || alert.debuggingSteps || []).map((step, i) => (
                        <li key={i}><ChevronRight size={14} className="step-bullet" /> {step}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {alert.confidence !== undefined && (
                  <div className="confidence-row">
                    <span className="section-label">AI Confidence</span>
                    <div className="confidence-bar-wrap">
                      <div className="confidence-bar" style={{ width: `${Math.round(alert.confidence * 100)}%` }} />
                    </div>
                    <span className="confidence-pct">{Math.round(alert.confidence * 100)}%</span>
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      <style>{`
        .component-container { height: 100%; display: flex; flex-direction: column; }
        .icon-orange { color: var(--warning-color); }
        .alert-count { background: var(--danger-color); color: white; font-size: 0.75rem; padding: 2px 8px; border-radius: 999px; margin-left: auto; font-weight: 600; }
        
        .alerts-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 1rem; padding-right: 0.5rem; }
        
        /* Custom scrollbar */
        .alerts-list::-webkit-scrollbar { width: 6px; }
        .alerts-list::-webkit-scrollbar-track { background: transparent; }
        .alerts-list::-webkit-scrollbar-thumb { background: #374151; border-radius: 3px; }
        
        .alert-card {
          background: rgba(255, 255, 255, 0.02);
          border: 1px solid var(--border-color);
          border-left-width: 4px;
          border-radius: 8px;
          padding: 1.25rem;
          transition: transform 0.2s;
        }
        
        .alert-card:hover { transform: translateX(2px); background: rgba(255, 255, 255, 0.04); }
        
        .severity-high, .severity-critical { border-left-color: var(--danger-color); }
        .severity-medium, .severity-warning { border-left-color: var(--warning-color); }
        .severity-low, .severity-info { border-left-color: var(--accent-color); }
        
        .severity-icon.critical { color: var(--danger-color); }
        .severity-icon.warning { color: var(--warning-color); }
        .severity-icon.info { color: var(--accent-color); }
        
        .alert-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem; }
        .alert-title { display: flex; align-items: flex-start; gap: 0.5rem; }
        .alert-title h3 { margin: 0; font-size: 1rem; color: var(--text-primary); line-height: 1.2; }
        .alert-time { font-size: 0.75rem; color: var(--text-secondary); white-space: nowrap; }
        
        .alert-body { display: flex; flex-direction: column; gap: 1rem; }
        .alert-section { display: flex; flex-direction: column; gap: 0.25rem; }
        .section-label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); font-weight: 600; }
        .alert-section p { font-size: 0.875rem; color: #d1d5db; margin: 0; }
        
        .steps-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.375rem; }
        .steps-list li { font-size: 0.875rem; color: #d1d5db; display: flex; align-items: flex-start; gap: 0.25rem; }
        .step-bullet { color: var(--accent-color); margin-top: 2px; flex-shrink: 0; }
        
        .all-clear-icon { font-size: 3rem; color: var(--success-color); margin-bottom: 1rem; opacity: 0.8; }
        
        .confidence-row { display: flex; align-items: center; gap: 0.5rem; margin-top: 0.25rem; }
        .confidence-bar-wrap { flex: 1; height: 4px; background: rgba(255,255,255,0.08); border-radius: 9999px; overflow: hidden; }
        .confidence-bar { height: 100%; background: linear-gradient(90deg, #3b82f6, #8b5cf6); border-radius: 9999px; transition: width 0.4s ease; }
        .confidence-pct { font-size: 0.75rem; font-weight: 600; color: #a78bfa; min-width: 2.5rem; text-align: right; }
      `}</style>
    </div>
  );
};

export default AlertPanel;
