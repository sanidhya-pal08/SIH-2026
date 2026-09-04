import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate, Link } from 'react-router-dom';
import { MapContainer, TileLayer, Marker, Popup, Polyline, GeoJSON } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import './App.css';
import api from './api';

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
            <label>Email Address</label>
            <input type="email" className="form-control" value={email} onChange={e => setEmail(e.target.value)} required placeholder="officer@nersahayak.gov.in" />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input type="password" className="form-control" value={password} onChange={e => setPassword(e.target.value)} required />
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

  const navigate = useNavigate();

  const userRole = localStorage.getItem('role') || 'Unknown';

  const fetchData = async () => {
    try {
      const reqRes = await api.get('/requests');
      setRequests(reqRes.data);
      
      const villRes = await api.get('/villages');
      const villObj = {};
      villRes.data.forEach(v => { villObj[v.id] = { name: v.name, coords: v.coords, id: v.id }; });
      setVillages(villObj);
      
      try {
        const geoRes = await api.get('/roads/geojson');
        setRoadsGeojson(geoRes.data);
      } catch (err) {
        console.warn("Could not fetch road geojson yet", err);
      }

      if (userRole === 'field_officer') {
        const roadRes = await api.get('/roads');
        setRoads(roadRes.data);
      }
      
      if (userRole === 'driver') {
        const delRes = await api.get('/deliveries');
        setDeliveries(delRes.data);
      }

      if (userRole === 'control_room') {
        try {
          const driverRes = await api.get('/users?role=driver');
          setDrivers(driverRes.data);
        } catch (e) {
          console.warn("Could not fetch drivers", e);
        }
      }
    } catch (err) {
      console.error("Fetch failed", err);
    }
  };

  useEffect(() => { fetchData(); }, [userRole]);

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
  const [incident, setIncident] = useState({ road_segment_id: '', incident_type: 'landslide' });
  const submitIncident = async (e) => {
    e.preventDefault();
    try {
      await api.post('/incidents', incident);
      alert("Incident Reported & Map Updated!");
    } catch(err) {
      alert("Failed to submit incident");
    }
  };

  // --- DRIVER FUNCTIONS ---
  const completeDelivery = async (id) => {
    try {
      await api.put(`/deliveries/${id}/pod`, { pod_notes: "Delivered safely." });
      alert("Proof of Delivery submitted!");
      fetchData();
    } catch(err) {
      alert("Failed to submit POD");
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
    return { color: '#3388ff', weight: 4 };
  };

  const onEachRoad = (feature, layer) => {
    const p = feature.properties;
    layer.bindPopup(
      `<strong>${p.name}</strong><br/>
       Status: ${p.accessibility_state ? p.accessibility_state.toUpperCase() : 'UNKNOWN'}<br/>
       Bridge: ${p.is_bridge ? 'Yes' : 'No'} ${p.is_bridge && p.max_vehicle_weight_kg ? `(Max ${p.max_vehicle_weight_kg/1000} T)` : ''}`
    );
  };

  return (
    <div className="dashboard">
      <div className="sidebar">
        <div className="sidebar-header">
          <h1>NER Sahayak</h1>
          <div className="header-controls">
            <span className="role-badge">{userRole.replace('_', ' ')}</span>
            <button className="logout-btn" onClick={handleLogout}>Logout</button>
          </div>
        </div>
        
        <div className="sidebar-content">
          
          {/* VIEW: CONTROL ROOM */}
          {userRole === 'control_room' && (
            <>
              <h2 className="section-title">Pending Requests</h2>
              {requests.filter(r => r.status === 'pending' || r.status === 'open').map(req => (
                <div key={req.id} className="request-card">
                  <div className="request-header" style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                    <div>
                      <span className="commodity" style={{display: 'block'}}>{req.commodity} ({req.quantity})</span>
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
                    <span className="commodity">{req.commodity}</span>
                    <span style={{fontSize: '0.8rem', fontWeight: 'bold'}}>{req.status.toUpperCase()}</span>
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
                  <label>Blocked Road</label>
                  <select className="form-control" value={incident.road_segment_id} onChange={e => setIncident({...incident, road_segment_id: e.target.value})} required>
                    <option value="">-- Select Road --</option>
                    {roads.map(r => <option key={r.id} value={r.id}>{r.name} ({r.accessibility_state})</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Incident Type</label>
                  <select className="form-control" value={incident.incident_type} onChange={e => setIncident({...incident, incident_type: e.target.value})}>
                    <option value="landslide">Landslide</option>
                    <option value="flood">Flood</option>
                    <option value="bridge_failure">Bridge Failure</option>
                  </select>
                </div>
                <button type="submit" className="dispatch-btn" style={{background: '#dc2626'}}>Report Hazard</button>
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
                  <button className="dispatch-btn" style={{background: '#10b981'}} onClick={() => completeDelivery(del.id)}>
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
                      <tr key={idx} style={{background: activeRouteIndex === idx ? '#eff6ff' : 'transparent'}}>
                        <td style={{padding: '8px', borderBottom: '1px solid #eee'}}>Rank {alt.rank}</td>
                        <td style={{padding: '8px', borderBottom: '1px solid #eee'}}>{alt.total_cost}</td>
                        <td style={{padding: '8px', borderBottom: '1px solid #eee'}}>
                          <button className="btn-secondary" style={{padding: '4px 8px', fontSize: '0.8rem'}} onClick={() => setActiveRouteIndex(idx)}>View Map</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                
                <div className="form-group">
                  <label>Assign Driver</label>
                  <select className="form-control" value={selectedDriver} onChange={e => setSelectedDriver(e.target.value)} required>
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
              <label>New Priority Score (0-100)</label>
              <input type="number" className="form-control" value={overrideScore} onChange={e => setOverrideScore(e.target.value)} min="0" max="100" required />
            </div>
            <div className="form-group">
              <label>Override Rationale (min 15 chars)</label>
              <textarea className="form-control" value={overrideReason} onChange={e => setOverrideReason(e.target.value)} minLength="15" required rows="3"></textarea>
            </div>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setOverrideTarget(null)}>Cancel</button>
              <button className="btn-primary" style={{background: '#dc2626'}} onClick={handleOverrideSubmit}>Apply Override</button>
            </div>
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
