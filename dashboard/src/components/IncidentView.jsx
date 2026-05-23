import React, { useState, useEffect } from 'react';
import { ShieldAlert, ServerCrash, Clock } from 'lucide-react';

const IncidentView = () => {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchIncidents = async () => {
      try {
        const response = await fetch('http://localhost:8000/logs');
        if (!response.ok) throw new Error('Failed to fetch logs');
        const logs = await response.json();
        
        // Group errors by endpoint
        const errors = logs.filter(log => log.status_code >= 400);
        const grouped = errors.reduce((acc, log) => {
          if (!acc[log.endpoint]) {
            acc[log.endpoint] = {
              endpoint: log.endpoint,
              count: 0,
              statusCodes: new Set(),
              firstSeen: new Date(log.timestamp),
              lastSeen: new Date(log.timestamp)
            };
          }
          
          acc[log.endpoint].count += 1;
          acc[log.endpoint].statusCodes.add(log.status_code);
          
          const logTime = new Date(log.timestamp);
          if (logTime < acc[log.endpoint].firstSeen) acc[log.endpoint].firstSeen = logTime;
          if (logTime > acc[log.endpoint].lastSeen) acc[log.endpoint].lastSeen = logTime;
          
          return acc;
        }, {});

        // Convert to array and format
        const formattedIncidents = Object.values(grouped).map(inc => {
          const duration = Math.round((inc.lastSeen - inc.firstSeen) / 1000); // seconds
          let timeWindow = duration < 60 
            ? `${duration}s` 
            : `${Math.floor(duration/60)}m ${duration%60}s`;
            
          if (duration === 0) timeWindow = "Instant";

          return {
            ...inc,
            statusCodes: Array.from(inc.statusCodes).join(', '),
            timeWindow
          };
        }).sort((a, b) => b.count - a.count); // Sort by most errors

        setIncidents(formattedIncidents);
      } catch (err) {
        console.error("Error fetching incidents", err);
      } finally {
        setLoading(false);
      }
    };

    fetchIncidents();
    const interval = setInterval(fetchIncidents, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="component-container">
      <h2 className="panel-title">
        <ShieldAlert size={20} className="icon-red" /> 
        Active Incidents
      </h2>
      
      <div className="incident-grid">
        {loading && incidents.length === 0 ? (
          <div className="loading">Detecting incidents...</div>
        ) : incidents.length === 0 ? (
          <div className="empty-state">
            <ShieldAlert size={32} style={{ color: 'var(--success-color)', marginBottom: '0.5rem' }} />
            <p>No active incidents</p>
          </div>
        ) : (
          incidents.map((incident, index) => (
            <div key={index} className="incident-card">
              <div className="incident-header">
                <div className="incident-endpoint">
                  <ServerCrash size={16} className="icon-red" />
                  <span className="endpoint-path">{incident.endpoint}</span>
                </div>
                <div className="error-badge">
                  {incident.count} Errors
                </div>
              </div>
              
              <div className="incident-details">
                <div className="detail-item">
                  <span className="detail-label">Status Codes</span>
                  <span className="detail-value status-codes">{incident.statusCodes}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Time Window</span>
                  <span className="detail-value flex-val">
                    <Clock size={12} /> {incident.timeWindow}
                  </span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <style>{`
        .component-container { height: 100%; display: flex; flex-direction: column; }
        .icon-red { color: var(--danger-color); }
        
        .incident-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
          gap: 1rem;
          margin-top: 0.5rem;
        }
        
        .incident-card {
          background: rgba(239, 68, 68, 0.05);
          border: 1px solid rgba(239, 68, 68, 0.2);
          border-radius: 8px;
          padding: 1rem;
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }
        
        .incident-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
        }
        
        .incident-endpoint {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          background: rgba(0, 0, 0, 0.2);
          padding: 0.25rem 0.5rem;
          border-radius: 4px;
          font-family: monospace;
          color: #f3f4f6;
          border: 1px solid #374151;
        }
        
        .error-badge {
          background: var(--danger-color);
          color: white;
          font-size: 0.75rem;
          font-weight: 600;
          padding: 0.25rem 0.5rem;
          border-radius: 9999px;
          box-shadow: 0 0 10px rgba(239, 68, 68, 0.3);
        }
        
        .incident-details {
          display: flex;
          justify-content: space-between;
          background: rgba(0, 0, 0, 0.2);
          border-radius: 6px;
          padding: 0.75rem;
        }
        
        .detail-item {
          display: flex;
          flex-direction: column;
          gap: 0.25rem;
        }
        
        .detail-label {
          font-size: 0.65rem;
          text-transform: uppercase;
          color: var(--text-secondary);
          letter-spacing: 0.05em;
        }
        
        .detail-value {
          font-size: 0.875rem;
          font-weight: 500;
          color: #e5e7eb;
        }
        
        .status-codes {
          color: #fbbf24;
          font-family: monospace;
        }
        
        .flex-val {
          display: flex;
          align-items: center;
          gap: 0.25rem;
        }
      `}</style>
    </div>
  );
};

export default IncidentView;
