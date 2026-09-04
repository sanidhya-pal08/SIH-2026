import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate, Link } from 'react-router-dom';
import { MapContainer, TileLayer, Marker, Popup, Polyline, GeoJSON, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import './App.css';
import api from './api';
import { enqueueAction, getActionsByStatus, countQueued, setCacheEntry, getCacheEntry } from './offlineDb.js';
import { initSync, triggerSync } from './syncWorker.js';

import AlertsPage from './AlertsPage.jsx';
import AuditTimelinePage from './AuditTimelinePage.jsx';
import { useTranslation } from './i18n.jsx';

import L from 'leaflet';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

function LocationPicker({ setLocation }) {
  useMapEvents({
    click(e) {
      setLocation({ lat: e.latlng.lat, lng: e.latlng.lng });
    }
  });
  return null;
}

function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const formData = new FormData();
      formData.append('username', email);
      formData.append('password', password);

      const res = await api.post('/auth/login', formData);
      localStorage.setItem('token', res.data.access_token);
      localStorage.setItem('role', res.data.role);
      navigate('/dashboard');
    } catch (err) {
      alert(err.response?.data?.detail || "Login failed. Ensure the backend Docker is running.");
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1>NER Sahayak</h1>
        <p>Log in to access your dashboard</p>
        <form onSubmit={handleLogin}>
          <div className="form-group">
            <label htmlFor="email">Email Address</label>
            <input id="email" type="email" className="form-control" value={email} onChange={e => setEmail(e.target.value)} required placeholder="officer@nersahayak.gov.in" />
          </div>
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input id="password" type="password" className="form-control" value={password} onChange={e => setPassword(e.target.value)} required />
          </div>
          <button type="submit" className="auth-btn">Log In</button>
        </form>
        <div className="auth-footer">
          Don't have an account? <Link to="/register" className="auth-link">Register here</Link>
        </div>
      </div>
    </div>
  );
}

function Register() {
  const [formData, setFormData] = useState({
    name: '', email: '', password: '', role: 'control_room', district: 'East Khasi Hills'
  });
  const navigate = useNavigate();

  const handleChange = (e) => setFormData({...formData, [e.target.name]: e.target.value});

  const handleRegister = async (e) => {
    e.preventDefault();
    try {
      await api.post('/auth/register', formData);
      alert("Registration successful! Please log in.");
      navigate('/login');
    } catch (err) {
      alert(err.response?.data?.detail || "Registration failed.");
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1>Register</h1>
        <p>Create a new NER Sahayak account</p>
        <form onSubmit={handleRegister}>
          <div className="form-group">
            <label>Full Name</label>
            <input type="text" name="name" className="form-control" onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>Email Address</label>
            <input type="email" name="email" className="form-control" onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input type="password" name="password" className="form-control" onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>Role</label>
            <select name="role" className="form-control" onChange={handleChange}>
              <option value="control_room">Control Room Officer</option>
              <option value="field_officer">Field Officer</option>
              <option value="driver">Driver / Carrier</option>
              <option value="village_rep">Village Representative</option>
            </select>
          </div>
          <button type="submit" className="auth-btn">Register</button>
        </form>
        <div className="auth-footer">
          Already have an account? <Link to="/login" className="auth-link">Log In</Link>
        </div>
      </div>
    </div>
  );
}

function Dashboard() {
  const { lang, setLang, t } = useTranslation();
  const [currentView, setCurrentView] = useState('dashboard');
  
  const [requests, setRequests] = useState([]);
  const [deliveries, setDeliveries] = useState([]);
  const [roads, setRoads] = useState([]);
  const [villages, setVillages] = useState({});
  const [roadsGeojson, setRoadsGeojson] = useState(null);
  
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [routePlan, setRoutePlan] = useState(null);
  const [activeRouteIndex, setActiveRouteIndex] = useState(0);
  const [selectedDriver, setSelectedDriver] = useState('');
  const [drivers, setDrivers] = useState([]);
  const [loading, setLoading] = useState(false);
  
  const [overrideTarget, setOverrideTarget] = useState(null);
  const [overrideScore, setOverrideScore] = useState('');
  const [overrideReason, setOverrideReason] = useState('');
  
  const [incidents, setIncidents] = useState([]);
  const [selectedLocation, setSelectedLocation] = useState(null);
  const [telemetryForm, setTelemetryForm] = useState({ checkpoint_name: '' });

  // POD Form State
  const [showPodModal, setShowPodModal] = useState(false);
  const [podTargetDelivery, setPodTargetDelivery] = useState(null);
  const [podForm, setPodForm] = useState({
    received_quantity: '',
    condition_status: 'intact',
    discrepancy_reason: '',
    receiver_name: '',
    receiver_contact: '',
    pod_notes: ''
  });
  const [podPhoto, setPodPhoto] = useState(null);

  // Offline state
  const [connectivity, setConnectivity] = useState('CONNECTED');
  const [queuedCount, setQueuedCount] = useState(0);
  const [lastSyncResult, setLastSyncResult] = useState(null);

  const navigate = useNavigate();

  const userRole = localStorage.getItem('role') || 'Unknown';

  const fetchData = async () => {
    try {
      try {
        const reqRes = await api.get('/requests');
        setRequests(reqRes.data);
      } catch (e) {
        console.warn("Could not fetch requests", e);
      }
      
      try {
        const villRes = await api.get('/villages');
        const villObj = {};
        villRes.data.forEach(v => { villObj[v.id] = { name: v.name, coords: v.coords, id: v.id }; });
        setVillages(villObj);
      } catch (e) {
        console.warn("Could not fetch villages", e);
      }
      
      try {
        const geoRes = await api.get('/roads/geojson');
        setRoadsGeojson(geoRes.data);
      } catch (err) {
        console.warn("Could not fetch road geojson yet", err);
      }

      if (userRole === 'field_officer') {
        try {
          const roadRes = await api.get('/roads');
          setRoads(roadRes.data);
        } catch (e) {
          console.warn("Could not fetch roads", e);
        }
      }
      
      if (userRole === 'driver') {
        try {
          const delRes = await api.get('/deliveries');
          setDeliveries(delRes.data);
          // Cache delivery data for offline use
          await setCacheEntry('my_deliveries', delRes.data).catch(() => {});
        } catch (e) {
          console.warn("Could not fetch deliveries", e);
          const cached = await getCacheEntry('my_deliveries').catch(() => null);
          if (cached) setDeliveries(cached.data);
        }
      }

      if (userRole === 'control_room') {
        try {
          const actDelRes = await api.get('/deliveries/active');
          setDeliveries(actDelRes.data);
        } catch (e) {
          console.warn("Could not fetch active deliveries", e);
        }
        try {
          const driverRes = await api.get('/users?role=driver');
          setDrivers(driverRes.data);
        } catch (e) {
          console.warn("Could not fetch drivers", e);
        }
        try {
          const incRes = await api.get('/incidents');
          setIncidents(incRes.data);
        } catch (e) {
          console.warn("Could not fetch incidents", e);
        }
      }
    } catch (err) {
      console.error("Fetch failed", err);
    }
  };

  useEffect(() => { 
    fetchData(); 
    if (userRole === 'control_room') {
      const interval = setInterval(fetchData, 10000);
      return () => clearInterval(interval);
    }
  }, [userRole]);

  // Initialise offline sync + listen for connectivity and sync-result events
  useEffect(() => {
    initSync().catch(console.warn);

    const onConnectivity = (e) => {
      setConnectivity(e.detail.state);
      setQueuedCount(e.detail.queuedCount);
    };
    const onSyncResult = (e) => {
      setLastSyncResult(e.detail);
      fetchData(); // refresh data after a successful sync
    };

    window.addEventListener('ner:connectivity', onConnectivity);
    window.addEventListener('ner:sync-result', onSyncResult);
    return () => {
      window.removeEventListener('ner:connectivity', onConnectivity);
      window.removeEventListener('ner:sync-result', onSyncResult);
    };
  }, []);

  // Set initial default for village_id when villages load
  useEffect(() => {
    if (Object.keys(villages).length > 0 && !newRequest.village_id) {
      setNewRequest(prev => ({ ...prev, village_id: Object.keys(villages)[0] }));
    }
  }, [villages]);

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    navigate('/login');
  };

  // --- CONTROL ROOM FUNCTIONS ---
  const handleDispatch = async (req) => {
    setLoading(true);
    try {
      const hq_id = Object.keys(villages)[0]; // Fallback to first village as HQ for MVP
      const res = await api.post('/routes/evaluate', {
        source_village_id: hq_id,
        target_village_id: req.village_id,
        vehicle_constraints: {},
        policy_weights: {}
      });
      setRoutePlan(res.data);
      setSelectedRequest(req);
    } catch (error) {
      console.error(error);
      alert("Route evaluation failed: " + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const confirmDispatch = async () => {
    if (!selectedDriver) {
      alert("Please select a driver to assign.");
      return;
    }
    
    const payload = {
      supply_request_id: selectedRequest.id,
      driver_id: selectedDriver,
      route_plan: {
        feasible: routePlan.feasible,
        summary: routePlan.summary,
        constraints_applied: routePlan.constraints_applied,
        recommendation: routePlan.recommendation,
        alternatives: routePlan.alternatives,
        chosen_alternative_index: activeRouteIndex
      }
    };
    
    try {
      await api.post('/deliveries', payload);
      alert("Delivery Dispatched successfully!");
      setRequests(requests.filter(r => r.id !== selectedRequest.id));
      setSelectedRequest(null);
      setRoutePlan(null);
      setActiveRouteIndex(0);
      setSelectedDriver('');
    } catch (error) {
      alert("Dispatch failed: " + (error.response?.data?.detail || error.message));
    }
  };

  const handleSyncWeather = async () => {
    try {
      await api.post('/environmental/sync');
      alert("Environmental data synced successfully!");
      fetchData();
    } catch (e) {
      alert("Failed to sync weather data.");
    }
  };

  // --- CONTROL ROOM FUNCTIONS (OVERRIDE) ---
  const handleOverrideSubmit = async () => {
    if (overrideReason.length < 15) {
      alert("Reason must be at least 15 characters long.");
      return;
    }
    try {
      await api.patch(`/requests/${overrideTarget.id}/override`, { 
        new_score: parseFloat(overrideScore), 
        override_reason: overrideReason 
      });
      alert("Priority successfully overridden!");
      setOverrideTarget(null);
      setOverrideScore('');
      setOverrideReason('');
      fetchData();
    } catch (err) {
      alert("Failed to override priority.");
    }
  };

  const handleVerifyConflict = async (incidentId, verifiedState) => {
    try {
      await api.post(`/incidents/${incidentId}/verify`, { verified_state: verifiedState, verification_note: "Verified by operator" });
      alert("State verified successfully.");
      fetchData();
    } catch(err) {
      alert("Failed to verify conflict");
    }
  };

  const getPriorityColor = (score) => {
    if (score >= 80) return '#dc2626'; // Critical (Red)
    if (score >= 50) return '#f97316'; // Urgent (Orange)
    return '#10b981'; // Routine (Green)
  };

  // --- HOSPITAL / VILLAGE REP FUNCTIONS ---
  const [newRequest, setNewRequest] = useState({ commodity_category: 'General', commodity: '', quantity: 10, urgency: 'routine', stockout_days: 0, village_id: '' });
  const submitRequest = async (e) => {
    e.preventDefault();
    try {
      await api.post('/requests', newRequest);
      alert("Supply Request Sent!");
      fetchData();
    } catch(err) {
      alert("Failed to submit request");
    }
  };

  // --- FIELD OFFICER FUNCTIONS ---
  const [incident, setIncident] = useState({ road_segment_id: '', incident_type: 'landslide', severity: 'medium', description: '' });
  const [incidentPhoto, setIncidentPhoto] = useState(null);

  const submitIncident = async (e) => {
    e.preventDefault();
    if (!selectedLocation) {
      alert("Please select a location on the map first.");
      return;
    }
    const payload = {
      road_segment_id: incident.road_segment_id,
      incident_type: incident.incident_type,
      severity: incident.severity,
      description: incident.description,
      latitude: selectedLocation.lat,
      longitude: selectedLocation.lng,
    };
    try {
      const formData = new FormData();
      Object.entries(payload).forEach(([k, v]) => formData.append(k, v));
      if (incidentPhoto) formData.append("photo", incidentPhoto);
      await api.post('/incidents', formData, { headers: { 'Content-Type': 'multipart/form-data' }});
      alert("Incident Reported & Map Updated!");
      setIncidentPhoto(null);
      setSelectedLocation(null);
      setIncident({ road_segment_id: '', incident_type: 'landslide', severity: 'medium', description: '' });
      fetchData();
    } catch(err) {
      // If network failed (not a 4xx validation error), queue for later sync
      const isNetworkError = !err.response;
      if (isNetworkError) {
        await enqueueAction({ action_type: 'incident.create', entity_type: 'incident', payload });
        const count = await countQueued();
        setQueuedCount(count);
        setConnectivity('OFFLINE');
        alert("No connectivity — incident saved locally. Will sync when back online.");
        setIncidentPhoto(null);
        setSelectedLocation(null);
        setIncident({ road_segment_id: '', incident_type: 'landslide', severity: 'medium', description: '' });
      } else {
        alert("Failed to submit incident: " + (err.response?.data?.detail || err.message));
      }
    }
  };

  // --- DRIVER FUNCTIONS ---
  const openPodModal = (delivery) => {
    setPodTargetDelivery(delivery);
    setPodForm({
      received_quantity: delivery.dispatched_quantity,
      condition_status: 'intact',
      discrepancy_reason: '',
      receiver_name: '',
      receiver_contact: '',
      pod_notes: ''
    });
    setPodPhoto(null);
    setShowPodModal(true);
  };

  const submitPod = async (e) => {
    e.preventDefault();
    const rq = parseInt(podForm.received_quantity, 10);
    const dq = podTargetDelivery.dispatched_quantity;
    
    if (rq > dq) {
      alert(`Cannot receive more than dispatched (${dq}).`);
      return;
    }
    if (rq < dq && !podForm.discrepancy_reason) {
      alert("A discrepancy reason is required for partial deliveries.");
      return;
    }

    try {
      const formData = new FormData();
      formData.append('received_quantity', rq);
      formData.append('condition_status', podForm.condition_status);
      if (podForm.discrepancy_reason) formData.append('discrepancy_reason', podForm.discrepancy_reason);
      if (podForm.receiver_name) formData.append('receiver_name', podForm.receiver_name);
      if (podForm.receiver_contact) formData.append('receiver_contact', podForm.receiver_contact);
      if (podForm.pod_notes) formData.append('pod_notes', podForm.pod_notes);
      if (podPhoto) formData.append('photo', podPhoto);

      await api.put(`/deliveries/${podTargetDelivery.id}/pod`, formData);
      alert("Proof of Delivery submitted!");
      setShowPodModal(false);
      fetchData();
    } catch(err) {
      const isNetworkError = !err.response;
      if (isNetworkError) {
        // Enqueue offline action (text fields only)
        const payload = {
          delivery_id: podTargetDelivery.id,
          received_quantity: rq,
          condition_status: podForm.condition_status,
          discrepancy_reason: podForm.discrepancy_reason,
          receiver_name: podForm.receiver_name,
          receiver_contact: podForm.receiver_contact,
          pod_notes: podForm.pod_notes
        };
        await enqueueAction({ action_type: 'delivery.pod', entity_type: 'delivery', payload });
        const count = await countQueued();
        setQueuedCount(count);
        setConnectivity('OFFLINE');
        alert("No connectivity — Proof of Delivery saved locally. Will sync when back online.");
        setShowPodModal(false);
      } else {
        alert("Failed to submit POD: " + (err.response?.data?.detail || err.message));
      }
    }
  };

  const sendGPSPing = async (deliveryId) => {
    if (!("geolocation" in navigator)) {
      alert("Geolocation is not supported by your browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(async (position) => {
      const telPayload = {
        delivery_id: deliveryId,
        source_type: 'mobile_gps',
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        speed_kmh: position.coords.speed ? (position.coords.speed * 3.6) : null,
        battery_level: null,
        checkpoint_name: null,
      };
      try {
        await api.post(`/deliveries/${deliveryId}/telemetry`, telPayload);
        alert("GPS telemetry sent successfully.");
        fetchData();
      } catch(e) {
        const isNetworkError = !e.response;
        if (isNetworkError) {
          await enqueueAction({ action_type: 'telemetry.create', entity_type: 'telemetry', payload: telPayload });
          const count = await countQueued();
          setQueuedCount(count);
          setConnectivity('OFFLINE');
          alert("No connectivity — GPS ping saved locally. Will sync when back online.");
        } else {
          alert("Failed to send GPS telemetry: " + (e.response?.data?.detail || e.message));
        }
      }
    }, (error) => {
      alert("Geolocation error: " + error.message);
    });
  };

  const submitManualCheckpoint = async (deliveryId) => {
    if (!telemetryForm.checkpoint_name) {
      alert("Enter a checkpoint name.");
      return;
    }
    const telPayload = {
      delivery_id: deliveryId,
      source_type: 'manual_checkpoint',
      latitude: selectedLocation ? selectedLocation.lat : 25.5788,
      longitude: selectedLocation ? selectedLocation.lng : 91.8933,
      speed_kmh: null,
      battery_level: null,
      checkpoint_name: telemetryForm.checkpoint_name,
    };
    try {
      await api.post(`/deliveries/${deliveryId}/telemetry`, telPayload);
      alert("Checkpoint logged.");
      setTelemetryForm({ checkpoint_name: '' });
      setSelectedLocation(null);
      fetchData();
    } catch(e) {
      const isNetworkError = !e.response;
      if (isNetworkError) {
        await enqueueAction({ action_type: 'telemetry.create', entity_type: 'telemetry', payload: telPayload });
        const count = await countQueued();
        setQueuedCount(count);
        setConnectivity('OFFLINE');
        alert("No connectivity — checkpoint saved locally. Will sync when back online.");
        setTelemetryForm({ checkpoint_name: '' });
        setSelectedLocation(null);
      } else {
        alert("Failed to log checkpoint: " + (e.response?.data?.detail || e.message));
      }
    }
  };


  const routeCoordinates = (routePlan && routePlan.alternatives && routePlan.alternatives.length > activeRouteIndex) 
    ? routePlan.alternatives[activeRouteIndex].coordinates 
    : [];

  const roadStyle = (feature) => {
    const state = feature.properties.accessibility_state;
    if (state === 'open') return { color: '#10b981', weight: 4 };
    if (state === 'hazardous') return { color: '#f59e0b', weight: 4, dashArray: '5, 5' };
    if (state === 'restricted') return { color: '#8b5cf6', weight: 4 };
    if (state === 'blocked') return { color: '#ef4444', weight: 4 };
    if (state === 'disputed') return { color: '#db2777', weight: 6, dashArray: '10, 10' };
    return { color: '#3388ff', weight: 4 };
  };

  const onEachRoad = (feature, layer) => {
    const p = feature.properties;
    let popupContent = `<strong>${p.name}</strong><br/>
       Status: ${p.accessibility_state ? p.accessibility_state.toUpperCase() : 'UNKNOWN'}<br/>
       Bridge: ${p.is_bridge ? 'Yes' : 'No'} ${p.is_bridge && p.max_vehicle_weight_kg ? `(Max ${p.max_vehicle_weight_kg/1000} T)` : ''}`;
       
    if (p.predicted_risk_band) {
       popupContent += `<br/><strong>Risk Band:</strong> <span style="color: ${p.predicted_risk_band === 'High' || p.predicted_risk_band === 'Severe' ? '#dc2626' : '#f59e0b'}">${p.predicted_risk_band}</span>`;
       if (p.disruption_probability !== undefined) {
         popupContent += ` (${(p.disruption_probability * 100).toFixed(1)}%)`;
       }
       if (p.risk_factors && p.risk_factors.length > 0) {
         popupContent += `<br/><strong>Risk Factors:</strong><ul style="margin: 2px 0; padding-left: 15px; font-size: 0.9em;"><li>${p.risk_factors.join('</li><li>')}</li></ul>`;
       }
    }
    
    layer.bindPopup(popupContent);
  };

  return (
    <div className="dashboard">
      <div className="sidebar">
        <div className="sidebar-header">
          <h1>{t('app.title')}</h1>
          <div className="header-controls">
            <select value={lang} onChange={e => setLang(e.target.value)} style={{ marginRight: '10px', padding: '2px' }}>
              <option value="en">EN</option>
              <option value="hi">HI</option>
            </select>
            <span className="role-badge">{userRole.replace('_', ' ')}</span>
            <button className="logout-btn" onClick={handleLogout}>{t('nav.logout')}</button>
          </div>
        </div>
        
        {/* ── Offline Status Banner ─────────────────────────────────────── */}
        {connectivity !== 'CONNECTED' && (
          <div style={{
            padding: '8px 12px',
            background: connectivity === 'SYNCING' ? '#dbeafe' : connectivity === 'OFFLINE' || connectivity === 'SERVER_UNAVAILABLE' ? '#fef2f2' : '#f0fdf4',
            borderBottom: '1px solid #e2e8f0',
            fontSize: '0.82rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <span>
              {connectivity === 'OFFLINE' && `🔴 OFFLINE · ${queuedCount} action${queuedCount !== 1 ? 's' : ''} queued`}
              {connectivity === 'SERVER_UNAVAILABLE' && `🟠 SERVER UNAVAILABLE · ${queuedCount} queued`}
              {connectivity === 'SYNCING' && `🔵 SYNCING · ${queuedCount} pending…`}
            </span>
            {connectivity !== 'SYNCING' && queuedCount > 0 && (
              <button style={{fontSize: '0.75rem', padding: '2px 8px', cursor: 'pointer'}} onClick={() => triggerSync()}>
                Retry Sync
              </button>
            )}
          </div>
        )}
        {connectivity === 'CONNECTED' && queuedCount === 0 && lastSyncResult && (
          <div style={{padding: '6px 12px', background: '#f0fdf4', borderBottom: '1px solid #e2e8f0', fontSize: '0.8rem', color: '#16a34a'}}>
            ✅ All changes synchronized
          </div>
        )}

        <div className="sidebar-content">
          {userRole === 'control_room' && (
            <div style={{ display: 'flex', gap: '10px', marginBottom: '15px', borderBottom: '1px solid #e2e8f0', paddingBottom: '10px' }}>
              <button className={currentView === 'dashboard' ? 'dispatch-btn' : 'btn-secondary'} onClick={() => setCurrentView('dashboard')}>{t('nav.dashboard')}</button>
              <button className={currentView === 'alerts' ? 'dispatch-btn' : 'btn-secondary'} onClick={() => setCurrentView('alerts')}>{t('nav.alerts')}</button>
              <button className={currentView === 'audit' ? 'dispatch-btn' : 'btn-secondary'} onClick={() => setCurrentView('audit')}>{t('nav.audit')}</button>
            </div>
          )}

          {currentView === 'alerts' && userRole === 'control_room' && <AlertsPage />}
          {currentView === 'audit' && userRole === 'control_room' && <AuditTimelinePage />}
          
          {/* VIEW: CONTROL ROOM (Dashboard) */}
          {currentView === 'dashboard' && userRole === 'control_room' && (
            <>
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px'}}>
                <h2 className="section-title" style={{margin: 0}}>Pending Requests</h2>
                <button className="btn-secondary" style={{fontSize: '0.8rem', background: '#f1f5f9'}} onClick={handleSyncWeather}>🌦️ Sync Weather Data</button>
              </div>
              {requests.filter(r => r.status === 'pending' || r.status === 'open').map(req => (
                <div key={req.id} className="request-card">
                  <div className="request-header" style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                    <div>
                      <span className="commodity" style={{display: 'block'}}>
                        {req.commodity} ({req.fulfilled_quantity || 0} / {req.quantity})
                        {req.parent_request_id && <span style={{marginLeft: '8px', fontSize: '0.75rem', background: '#f59e0b', color: 'white', padding: '2px 6px', borderRadius: '10px'}}>Follow-up</span>}
                      </span>
                      <span className={`urgency-badge urgency-${req.urgency}`}>{req.urgency}</span>
                    </div>
                    <div style={{display: 'flex', gap: '10px', alignItems: 'center'}}>
                      <span 
                        className="priority-chip" 
                        style={{ background: getPriorityColor(req.priority_score), color: 'white', padding: '4px 10px', borderRadius: '12px', fontSize: '0.9rem', cursor: 'help', fontWeight: 'bold' }}
                        title={req.priority_breakdown ? JSON.stringify(req.priority_breakdown, null, 2) : 'No breakdown available'}
                      >
                        Score: {req.priority_score?.toFixed(1)} {req.is_overridden && '⚠️'}
                      </span>
                      <button className="btn-secondary" style={{padding: '4px 10px', fontSize: '0.8rem', background: '#e2e8f0', color: '#1e293b'}} onClick={() => { setOverrideTarget(req); setOverrideScore(req.priority_score); }}>Override</button>
                    </div>
                  </div>
                  <div className="village-name">Destination: {villages[req.village_id]?.name || 'Unknown'}</div>
                  <button className="dispatch-btn" onClick={() => handleDispatch(req)} disabled={loading}>
                    {loading ? 'Evaluating...' : 'Evaluate Route & Dispatch'}
                  </button>
                </div>
              ))}
              {requests.length === 0 && <p>No pending requests.</p>}
              
              {roadsGeojson?.features.filter(f => f.properties.accessibility_state === 'disputed').length > 0 && (
                <h2 className="section-title">Disputed Roads</h2>
              )}
              {roadsGeojson?.features.filter(f => f.properties.accessibility_state === 'disputed').map(road => {
                 const relatedIncidents = incidents.filter(i => i.road_segment_id === road.properties.id && i.status === 'pending_review');
                 const backendUrl = api.defaults.baseURL ? api.defaults.baseURL.replace('/api/v1', '') : 'http://localhost:8000';
                 return (
                   <div key={road.properties.id} className="request-card" style={{borderLeft: '4px solid #db2777'}}>
                     <h3 style={{marginTop: 0}}>DISPUTED: {road.properties.name || 'Unnamed Road'}</h3>
                     {relatedIncidents.map(inc => (
                        <div key={inc.id} style={{marginBottom: '10px', padding: '10px', background: '#f8fafc', borderRadius: '4px'}}>
                           <strong>{inc.incident_type} ({inc.severity})</strong> - Conf: {inc.confidence_score}<br/>
                           {inc.description}<br/>
                           {inc.evidence_url && <a href={`${backendUrl}${inc.evidence_url}`} target="_blank" rel="noreferrer" style={{color: '#2563eb'}}>View Photo</a>}
                           <div style={{marginTop: '5px'}}>
                             <button className="btn-secondary" style={{marginRight: '10px', background: '#fee2e2'}} onClick={() => handleVerifyConflict(inc.id, 'blocked')}>Verify Blocked</button>
                             <button className="btn-secondary" style={{background: '#d1fae5'}} onClick={() => handleVerifyConflict(inc.id, 'open')}>Verify Open</button>
                           </div>
                        </div>
                     ))}
                   </div>
                 );
              })}
            </>
          )}

          {/* VIEW: HOSPITAL / VILLAGE REP */}
          {userRole === 'village_rep' && (
            <>
              <h2 className="section-title">Request Supplies</h2>
              <form onSubmit={submitRequest} style={{background: 'white', padding: '15px', borderRadius: '8px', marginBottom: '20px', border: '1px solid #e2e8f0'}}>
                <div className="form-group">
                  <label>Commodity Category</label>
                  <select className="form-control" value={newRequest.commodity_category} onChange={e => setNewRequest({...newRequest, commodity_category: e.target.value})}>
                    <option value="Medical/Blood/O2">Medical / Blood / O2</option>
                    <option value="Drinking Water">Drinking Water</option>
                    <option value="Food">Food</option>
                    <option value="General">General / Others</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Commodity Item Name</label>
                  <input type="text" className="form-control" value={newRequest.commodity} onChange={e => setNewRequest({...newRequest, commodity: e.target.value})} required placeholder="e.g. Oxygen Cylinders" />
                </div>
                <div className="form-group">
                  <label>Quantity</label>
                  <input type="number" className="form-control" value={newRequest.quantity} onChange={e => setNewRequest({...newRequest, quantity: e.target.value})} required />
                </div>
                <div className="form-group">
                  <label>Urgency</label>
                  <select className="form-control" value={newRequest.urgency} onChange={e => setNewRequest({...newRequest, urgency: e.target.value})}>
                    <option value="routine">Routine</option>
                    <option value="urgent">Urgent</option>
                    <option value="emergency">Emergency</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Stockout Days (Remaining days of supply)</label>
                  <input type="number" className="form-control" min="0" value={newRequest.stockout_days} onChange={e => setNewRequest({...newRequest, stockout_days: parseInt(e.target.value)})} required />
                </div>
                <div className="form-group">
                  <label>Your Location</label>
                  <select className="form-control" value={newRequest.village_id} onChange={e => setNewRequest({...newRequest, village_id: e.target.value})}>
                    {Object.entries(villages).map(([id, v]) => <option key={id} value={id}>{v.name}</option>)}
                  </select>
                </div>
                <button type="submit" className="dispatch-btn">Submit Request</button>
              </form>

              <h2 className="section-title">My Recent Requests</h2>
              {requests.map(req => (
                <div key={req.id} className="request-card">
                  <div className="request-header">
                    <span className="commodity">
                      {req.commodity} ({req.fulfilled_quantity || 0} / {req.quantity})
                      {req.parent_request_id && <span style={{marginLeft: '8px', fontSize: '0.75rem', background: '#f59e0b', color: 'white', padding: '2px 6px', borderRadius: '10px'}}>Follow-up</span>}
                    </span>
                    <span style={{fontSize: '0.8rem', fontWeight: 'bold'}}>{req.status.replace('_', ' ').toUpperCase()}</span>
                  </div>
                </div>
              ))}
            </>
          )}

          {/* VIEW: FIELD OFFICER */}
          {userRole === 'field_officer' && (
            <>
              <h2 className="section-title">Report Incident</h2>
              <p style={{fontSize: '0.9rem', marginBottom: '15px', color: '#64748b'}}>Select a road block to instantly trigger AI re-routing.</p>
              <form onSubmit={submitIncident} style={{background: 'white', padding: '15px', borderRadius: '8px', border: '1px solid #e2e8f0'}}>
                <div className="form-group">
                  <label>Road Segment</label>
                  <select className="form-control" value={incident.road_segment_id} onChange={e => setIncident({...incident, road_segment_id: e.target.value})} required>
                    <option value="">-- Select Road --</option>
                    {roadsGeojson?.features.map(f => <option key={f.properties.id} value={f.properties.id}>{f.properties.name || 'Unnamed'} ({f.properties.accessibility_state})</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Incident Type</label>
                  <select className="form-control" value={incident.incident_type} onChange={e => setIncident({...incident, incident_type: e.target.value})}>
                    <option value="landslide">Landslide</option>
                    <option value="flood">Flood</option>
                    <option value="bridge_failure">Bridge Failure</option>
                    <option value="road_damage">Road Damage</option>
                    <option value="obstruction">Obstruction</option>
                    <option value="reopened">Reopened/Open</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Severity</label>
                  <select className="form-control" value={incident.severity} onChange={e => setIncident({...incident, severity: e.target.value})}>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Description</label>
                  <textarea className="form-control" value={incident.description} onChange={e => setIncident({...incident, description: e.target.value})} required />
                </div>
                <div className="form-group">
                  <label>Photo Evidence</label>
                  <input type="file" className="form-control" accept="image/jpeg, image/png" onChange={e => setIncidentPhoto(e.target.files[0])} />
                </div>
                <div className="form-group">
                  <label>Location</label>
                  <div style={{fontSize: '0.9rem', color: '#64748b'}}>
                    {selectedLocation ? `Lat: ${selectedLocation.lat.toFixed(4)}, Lng: ${selectedLocation.lng.toFixed(4)}` : 'Click on the map to select location'}
                  </div>
                </div>
                <button type="submit" className="dispatch-btn" style={{background: '#dc2626'}}>Report Incident</button>
              </form>
            </>
          )}

          {/* VIEW: DRIVER */}
          {userRole === 'driver' && (
            <>
              <h2 className="section-title">Active Deliveries</h2>
              {deliveries.filter(d => d.status === 'dispatched').map(del => (
                <div key={del.id} className="request-card">
                  <div className="request-header">
                    <span className="commodity">Delivery #{del.id.substring(0,4)}</span>
                  </div>
                  <p style={{fontSize: '0.9rem', marginBottom: '10px'}}>Follow AI Recommended Route.</p>
                  
                  <div style={{background: '#f8fafc', padding: '10px', borderRadius: '4px', marginBottom: '10px'}}>
                    <h4 style={{marginTop: 0, marginBottom: '10px'}}>Telemetry & Progress</h4>
                    <button className="btn-secondary" style={{width: '100%', marginBottom: '10px', background: '#3b82f6', color: 'white'}} onClick={() => sendGPSPing(del.id)}>
                      📍 Transmit GPS Ping
                    </button>
                    <div style={{display: 'flex', gap: '5px'}}>
                      <input 
                        type="text" 
                        placeholder="Checkpoint Name" 
                        className="form-control" 
                        value={telemetryForm.checkpoint_name}
                        onChange={e => setTelemetryForm({ checkpoint_name: e.target.value })}
                        style={{flex: 1, minWidth: '100px'}}
                      />
                      <button className="btn-secondary" style={{whiteSpace: 'nowrap'}} onClick={() => submitManualCheckpoint(del.id)}>Log Checkpoint</button>
                    </div>
                    <small style={{display: 'block', marginTop: '5px', color: '#64748b'}}>* For manual checkpoints, select location on map first.</small>
                  </div>

                  <button className="dispatch-btn" style={{background: '#10b981'}} onClick={() => openPodModal(del)}>
                    Submit Proof of Delivery
                  </button>
                </div>
              ))}
              {deliveries.filter(d => d.status === 'dispatched').length === 0 && <p>No active deliveries.</p>}
            </>
          )}

        </div>
      </div>

      <div className="map-area">
        <MapContainer center={[25.5788, 91.8933]} zoom={10} scrollWheelZoom={true}>
          <TileLayer attribution='&copy; OpenStreetMap' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          
          {roadsGeojson && (
            <GeoJSON 
              data={roadsGeojson} 
              style={roadStyle} 
              onEachFeature={onEachRoad}
            />
          )}

          {Object.entries(villages).map(([key, data]) => (
            <Marker key={key} position={data.coords}>
              <Popup>{data.name}</Popup>
            </Marker>
          ))}
          {routeCoordinates.length > 0 && (
            <Polyline positions={routeCoordinates} color="#2563eb" weight={5} />
          )}
          {(userRole === 'field_officer' || userRole === 'driver') && <LocationPicker setLocation={setSelectedLocation} />}
          {selectedLocation && (
            <Marker position={[selectedLocation.lat, selectedLocation.lng]}>
              <Popup>Selected Location</Popup>
            </Marker>
          )}
          
          {/* VEHICLE MARKERS */}
          {deliveries.filter(d => d.status === 'dispatched' && d.last_known_lat).map(del => {
            let statusColor = '#10b981'; // FRESH
            let statusText = 'FRESH';
            if (del.deviation_status === 'deviated') {
              statusColor = '#ef4444'; // DEVIATED
              statusText = 'DEVIATED';
            } else if (del.last_ping_at && (new Date() - new Date(del.last_ping_at)) > 30 * 60 * 1000) {
              statusColor = '#94a3b8'; // STALE
              statusText = 'STALE';
            }
            
            const markerHtml = `<div style="background-color: ${statusColor}; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 4px rgba(0,0,0,0.4);"></div>`;
            const customIcon = L.divIcon({ html: markerHtml, className: 'vehicle-marker', iconSize: [22, 22], iconAnchor: [11, 11] });
            
            return (
              <Marker key={del.id} position={[del.last_known_lat, del.last_known_lng]} icon={customIcon}>
                <Popup>
                  <strong>Delivery #{del.id.substring(0,4)}</strong><br/>
                  Status: <span style={{color: statusColor, fontWeight: 'bold'}}>{statusText}</span><br/>
                  Last Ping: {del.last_ping_at ? new Date(del.last_ping_at).toLocaleTimeString() : 'Unknown'}
                </Popup>
              </Marker>
            );
          })}
        </MapContainer>
      </div>

      {selectedRequest && routePlan && (
        <div className="modal-overlay">
          <div className="modal-content" style={{maxWidth: '600px'}}>
            <h2>Route Evaluation Complete</h2>
            <div className="route-rationale" style={{marginBottom: '15px'}}>
              <strong>Rationale:</strong> {routePlan.summary}
              {routePlan.constraints_applied && routePlan.constraints_applied.length > 0 && (
                <div style={{color: '#dc2626', marginTop: '10px', fontSize: '0.9rem'}}>
                  <strong>Constraints Applied:</strong>
                  <ul style={{marginTop: '5px', paddingLeft: '20px'}}>
                    {routePlan.constraints_applied.map((c, i) => <li key={i}>{c.reason}</li>)}
                  </ul>
                </div>
              )}
            </div>
            
            {routePlan.feasible && (
              <>
                <table style={{width: '100%', marginBottom: '15px', borderCollapse: 'collapse'}}>
                  <thead>
                    <tr>
                      <th style={{borderBottom: '1px solid #ccc', padding: '8px', textAlign: 'left'}}>Option</th>
                      <th style={{borderBottom: '1px solid #ccc', padding: '8px', textAlign: 'left'}}>Cost</th>
                      <th style={{borderBottom: '1px solid #ccc', padding: '8px', textAlign: 'left'}}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {routePlan.alternatives.map((alt, idx) => (
                      <tr key={idx} style={{background: activeRouteIndex === idx ? '#eff6ff' : (alt.is_wait_window ? '#fef2f2' : 'transparent')}}>
                        <td style={{padding: '8px', borderBottom: '1px solid #eee'}}>
                          {alt.is_wait_window ? <span style={{color: '#dc2626', fontWeight: 'bold'}}>WAIT ADVISORY</span> : `Rank ${alt.rank}`}
                        </td>
                        <td style={{padding: '8px', borderBottom: '1px solid #eee'}}>{alt.total_cost}</td>
                        <td style={{padding: '8px', borderBottom: '1px solid #eee'}}>
                          {!alt.is_wait_window && (
                            <button className="btn-secondary" style={{padding: '4px 8px', fontSize: '0.8rem'}} onClick={() => setActiveRouteIndex(idx)}>View Map</button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                
                <div className="form-group">
                  <label htmlFor="assign-driver">Assign Driver</label>
                  <select id="assign-driver" className="form-control" value={selectedDriver} onChange={e => setSelectedDriver(e.target.value)} required>
                    <option value="">-- Select Driver --</option>
                    {drivers.map(d => (
                      <option key={d.id} value={d.id}>{d.name}</option>
                    ))}
                  </select>
                </div>
              </>
            )}
            
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => { setSelectedRequest(null); setRoutePlan(null); setActiveRouteIndex(0); setSelectedDriver(''); }}>Cancel</button>
              {routePlan.feasible && (
                <button className="btn-primary" onClick={confirmDispatch} disabled={!selectedDriver}>Approve & Dispatch</button>
              )}
            </div>
          </div>
        </div>
      )}

      {overrideTarget && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h2>Override Priority Score</h2>
            <p>Manually adjust the priority for: <strong>{overrideTarget.commodity}</strong></p>
            <div className="form-group">
              <label htmlFor="override-score">New Priority Score (0-100)</label>
              <input id="override-score" type="number" className="form-control" value={overrideScore} onChange={e => setOverrideScore(e.target.value)} min="0" max="100" required />
            </div>
            <div className="form-group">
              <label htmlFor="override-reason">Override Rationale (min 15 chars)</label>
              <textarea id="override-reason" className="form-control" value={overrideReason} onChange={e => setOverrideReason(e.target.value)} minLength="15" required rows="3"></textarea>
            </div>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setOverrideTarget(null)}>Cancel</button>
              <button className="btn-primary" style={{background: '#dc2626'}} onClick={handleOverrideSubmit}>Apply Override</button>
            </div>
          </div>
        </div>
      )}

      {showPodModal && podTargetDelivery && (
        <div className="modal-overlay">
          <div className="modal-content" style={{maxHeight: '90vh', overflowY: 'auto'}}>
            <h2>Submit Proof of Delivery</h2>
            <p>Delivery #{podTargetDelivery.id.substring(0,8)}</p>
            <p style={{marginBottom: '15px'}}>Dispatched Quantity: <strong>{podTargetDelivery.dispatched_quantity}</strong></p>
            <form onSubmit={submitPod}>
              <div className="form-group">
                <label>Received Quantity</label>
                <input 
                  type="number" 
                  className="form-control" 
                  value={podForm.received_quantity} 
                  onChange={e => setPodForm({...podForm, received_quantity: e.target.value})} 
                  min="0" 
                  max={podTargetDelivery.dispatched_quantity} 
                  required 
                />
              </div>
              <div className="form-group">
                <label>Condition</label>
                <select 
                  className="form-control" 
                  value={podForm.condition_status} 
                  onChange={e => setPodForm({...podForm, condition_status: e.target.value})}
                >
                  <option value="intact">Intact / Good Condition</option>
                  <option value="damaged">Damaged / Poor Condition</option>
                  <option value="partial">Partial / Shortage</option>
                </select>
              </div>
              
              {/* Show reason if discrepancy exists */}
              {(parseInt(podForm.received_quantity, 10) < podTargetDelivery.dispatched_quantity || podForm.condition_status !== 'intact') && (
                <div className="form-group">
                  <label>Discrepancy / Damage Reason <span style={{color: 'red'}}>*</span></label>
                  <textarea 
                    className="form-control" 
                    value={podForm.discrepancy_reason} 
                    onChange={e => setPodForm({...podForm, discrepancy_reason: e.target.value})} 
                    required={parseInt(podForm.received_quantity, 10) < podTargetDelivery.dispatched_quantity}
                    rows="2"
                    placeholder="Explain the shortage or damage..."
                  ></textarea>
                </div>
              )}

              <div className="form-group">
                <label>Receiver Name</label>
                <input 
                  type="text" 
                  className="form-control" 
                  value={podForm.receiver_name} 
                  onChange={e => setPodForm({...podForm, receiver_name: e.target.value})} 
                  placeholder="Optional"
                />
              </div>
              
              <div className="form-group">
                <label>Photo Evidence</label>
                <input 
                  type="file" 
                  className="form-control" 
                  accept="image/jpeg, image/png" 
                  onChange={e => setPodPhoto(e.target.files[0])} 
                />
                <small style={{display: 'block', marginTop: '4px', color: '#64748b'}}>* Photos cannot be synchronized while offline.</small>
              </div>

              <div className="modal-actions" style={{marginTop: '20px'}}>
                <button type="button" className="btn-secondary" onClick={() => setShowPodModal(false)}>Cancel</button>
                <button type="submit" className="btn-primary" style={{background: '#10b981'}}>Confirm Delivery</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem('token');
  return token ? children : <Navigate to="/login" replace />;
};

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
