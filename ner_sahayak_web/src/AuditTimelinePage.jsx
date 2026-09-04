import React, { useState } from 'react';
import api from './api';
import { useTranslation } from './i18n';

export default function AuditTimelinePage() {
  const { t } = useTranslation();
  const [correlationId, setCorrelationId] = useState('');
  const [events, setEvents] = useState([]);
  const [searched, setSearched] = useState(false);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!correlationId) return;
    try {
      const res = await api.get(`/audit/timeline/${correlationId}`);
      setEvents(res.data);
      setSearched(true);
    } catch (err) {
      alert("Failed to fetch audit timeline.");
    }
  };

  const handleExport = () => {
    const backendUrl = api.defaults.baseURL ? api.defaults.baseURL.replace('/api/v1', '') : 'http://localhost:8000';
    window.open(`${backendUrl}/api/v1/audit/export?correlation_id=${correlationId}`, '_blank');
  };

  return (
    <div style={{ padding: '20px' }}>
      <h1 className="section-title">{t('audit.title')}</h1>
      <form onSubmit={handleSearch} style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
        <input 
          type="text" 
          className="form-control" 
          placeholder="Enter Delivery ID or Request ID..." 
          value={correlationId} 
          onChange={e => setCorrelationId(e.target.value)} 
          style={{ width: '300px' }} 
        />
        <button type="submit" className="dispatch-btn" style={{ width: 'auto' }}>Search</button>
        {searched && <button type="button" className="btn-secondary" onClick={handleExport}>Export CSV</button>}
      </form>

      {searched && events.length === 0 && <p>No events found for this ID.</p>}
      
      {events.length > 0 && (
        <div className="timeline" style={{ borderLeft: '2px solid #e2e8f0', marginLeft: '20px', paddingLeft: '20px' }}>
          {events.map((evt, idx) => (
            <div key={evt.event_id} style={{ position: 'relative', marginBottom: '20px' }}>
              <div style={{ 
                position: 'absolute', left: '-27px', top: '0', 
                width: '12px', height: '12px', borderRadius: '50%', 
                background: evt.integrity_verified ? '#10b981' : '#dc2626' 
              }}></div>
              <div className="request-card" style={{ marginLeft: '10px', padding: '10px 15px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                  <strong>{evt.event_type}</strong>
                  <span style={{ fontSize: '0.8rem', color: '#64748b' }}>{new Date(evt.occurred_at).toLocaleString()}</span>
                </div>
                <div style={{ fontSize: '0.85rem', color: '#334155', background: '#f8fafc', padding: '8px', borderRadius: '4px' }}>
                  <pre style={{ margin: 0 }}>{JSON.stringify(evt.payload, null, 2)}</pre>
                </div>
                <div style={{ marginTop: '5px', fontSize: '0.75rem', color: evt.integrity_verified ? '#10b981' : '#dc2626' }}>
                  {evt.integrity_verified ? `✅ ${t('audit.verified')} (Hash: ${evt.checksum.substring(0, 8)}...)` : `❌ ${t('audit.invalid')}`}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
