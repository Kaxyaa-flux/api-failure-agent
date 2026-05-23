import React from 'react';
import LogsTable from './components/LogsTable';
import LatencyChart from './components/LatencyChart';
import AlertPanel from './components/AlertPanel';
import IncidentView from './components/IncidentView';
import './App.css';

function App() {
  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>AI-Powered API Failure Detection</h1>
        <div className="status-indicator">
          <span className="pulse-dot"></span> Live
        </div>
      </header>
      
      <main className="dashboard-grid">
        <div className="grid-item incident-view">
          <IncidentView />
        </div>
        
        <div className="grid-item alert-panel">
          <AlertPanel />
        </div>
        
        <div className="grid-item latency-chart">
          <LatencyChart />
        </div>
        
        <div className="grid-item logs-table">
          <LogsTable />
        </div>
      </main>
    </div>
  );
}

export default App;
