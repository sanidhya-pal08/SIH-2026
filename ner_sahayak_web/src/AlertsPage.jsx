import React, { useState, useEffect } from 'react';
import api from './api';
import { useTranslation } from './i18n';

export default function AlertsPage() {
  const { t } = useTranslation();
  const [alerts, setAlerts] = useState([]);

  const fetchAlerts = async () => {
    try {
      const res = await api.get('/alerts');
      setAlerts(res.data);
    } catch (e) {
      console.warn("Failed to fetch alerts", e);
    }
  };

  useEffect(() => {
    fetchAlerts();
    const int = setInterval(fetchAlerts, 10000);
    return () => clearInterval(int);
  }, []);

  const handleAcknowledge = async (id) => {
    try {
      await api.post(`/alerts/${id}/acknowledge`);
      fetchAlerts();
    } catch (e) {
      alert("Failed to acknowledge alert");
    }
  };

  const handleEscalate = async (id, decision) => {
    try {
      const reason = prompt("Enter reason for escalation decision:");
      if (!reason) return;
      await api.post(`/alerts/${id}/escalate`, { reason, decision });
      alert("Escalation action recorded.");
      fetchAlerts();
    } catch (e) {
      alert("Failed to escalate alert");
    }
  };

  return (
    <div style={{ padding: '20px' }}>
      <h1 className="section-title">{t('alert.title')}</h1>
      {alerts.length === 0 ? (
        <p>No active alerts.</p>
      ) : (
        alerts.map(alert => (
          <div key={alert.id} className="request-card" style={{ borderLeft: '4px solid #dc2626' }}>
            <h3 style={{ marginTop: 0, color: '#dc2626' }}>{alert.title}</h3>
            <p>{alert.message}</p>
            {alert.recommendation_payload?.handoff_village_name && (
              <p><strong>Recommendation:</strong> Escalate to air delivery or handoff at {alert.recommendation_payload.handoff_village_name}</p>
            )}
            <div style={{ marginTop: '10px' }}>
              <button className="btn-secondary" style={{ marginRight: '10px', background: '#e2e8f0' }} onClick={() => handleAcknowledge(alert.id)}>
                {t('alert.acknowledge')}
              </button>
              <button className="dispatch-btn" style={{ background: '#f59e0b' }} onClick={() => handleEscalate(alert.id, 'approved')}>
                {t('alert.escalate')}
              </button>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
