import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceArea } from 'recharts';
import { Activity } from 'lucide-react';

const CustomDot = (props) => {
  const { cx, cy, payload } = props;
  
  if (payload.isAnomaly) {
    return (
      <circle cx={cx} cy={cy} r={6} stroke="rgba(239, 68, 68, 0.5)" strokeWidth={4} fill="#ef4444" />
    );
  }
  return <circle cx={cx} cy={cy} r={3} stroke="none" fill="#3b82f6" />;
};

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="chart-tooltip">
        <p className="tooltip-time">{new Date(data.timestamp).toLocaleTimeString()}</p>
        <p className="tooltip-val">Latency: <span>{parseFloat(data.latency).toFixed(2)}ms</span></p>
        {data.isAnomaly && <p className="tooltip-alert">⚠️ Anomaly Detected</p>}
      </div>
    );
  }
  return null;
};

const LatencyChart = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [logsRes, anomaliesRes] = await Promise.all([
          fetch('http://localhost:8000/logs').catch(() => ({ ok: false })),
          fetch('http://localhost:8000/anomalies').catch(() => ({ ok: false }))
        ]);

        let logs = [];
        let anomalies = [];
        
        if (logsRes.ok) logs = await logsRes.json();
        if (anomaliesRes.ok) anomalies = await anomaliesRes.json();

        // Sort logs by timestamp ascending for the chart
        const sortedLogs = logs.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
        
        // Merge anomalies
        const chartData = sortedLogs.map(log => {
          const isAnomaly = anomalies.some(a => 
            a.timestamp === log.timestamp || 
            Math.abs(new Date(a.timestamp) - new Date(log.timestamp)) < 1000
          );
          return {
            ...log,
            time: new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second:'2-digit' }),
            isAnomaly
          };
        });

        setData(chartData.slice(-30)); // Show last 30 points
      } catch (err) {
        console.error("Error fetching chart data", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="component-container">
      <h2 className="panel-title"><Activity size={20} className="icon-purple" /> Latency Trends</h2>
      
      <div className="chart-wrapper">
        {loading && data.length === 0 ? (
          <div className="loading">Loading chart...</div>
        ) : data.length === 0 ? (
          <div className="empty-state">No latency data available</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2e323a" vertical={false} />
              <XAxis 
                dataKey="time" 
                stroke="#a0a5b1" 
                fontSize={12} 
                tickLine={false}
                axisLine={false}
              />
              <YAxis 
                stroke="#a0a5b1" 
                fontSize={12}
                tickLine={false}
                axisLine={false}
                tickFormatter={(val) => `${val}ms`}
              />
              <Tooltip content={<CustomTooltip />} />
              <Line 
                type="monotone" 
                dataKey="latency" 
                stroke="#8b5cf6" 
                strokeWidth={3}
                dot={<CustomDot />}
                activeDot={{ r: 8, strokeWidth: 0, fill: '#c4b5fd' }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <style>{`
        .component-container { height: 100%; display: flex; flex-direction: column; }
        .icon-purple { color: #8b5cf6; }
        .chart-wrapper { flex: 1; min-height: 250px; margin-top: 1rem; }
        
        .chart-tooltip {
          background: var(--panel-bg);
          border: 1px solid var(--border-color);
          padding: 0.75rem 1rem;
          border-radius: 8px;
          box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
        }
        .tooltip-time { font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 0.25rem; }
        .tooltip-val { font-weight: 500; font-size: 0.875rem; color: var(--text-primary); }
        .tooltip-val span { color: #8b5cf6; }
        .tooltip-alert { margin-top: 0.5rem; color: var(--danger-color); font-size: 0.75rem; font-weight: 600; display: flex; align-items: center; gap: 0.25rem; }
      `}</style>
    </div>
  );
};

export default LatencyChart;
