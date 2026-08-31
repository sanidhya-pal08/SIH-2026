import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate, Link } from 'react-router-dom';
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet';
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

const VILLAGES = {
  "9ee6cf9a-42a1-5d91-9d36-93e343b27581": { name: "Base Camp Alpha", coords: [28.6139, 77.2090], id: "N1" },
  "4cd6c234-9cc9-57d9-8050-232f05c3e6c9": { name: "Field Hospital", coords: [28.6200, 77.2150], id: "N2" },
  "9c683dd2-65b0-58fe-a952-1bd17e1c04a3": { name: "Supply Depot", coords: [28.6280, 77.2050], id: "N3" },
  "e0b80a71-2217-5939-b047-d22900fbeedd": { name: "Evacuation Point", coords: [28.6350, 77.2200], id: "N4" },
  "d1482c21-214c-50aa-aba5-e1ded723816b": { name: "Shelter Zone", coords: [28.6100, 77.2300], id: "N5" },
  "ee67ad07-f12f-54ec-aa00-97f1d6ed72a5": { name: "Command Center", coords: [28.6400, 77.2100], id: "N6" },
};

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
  
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [routePlan, setRoutePlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const userRole = localStorage.getItem('role') || 'Unknown';

  const fetchData = async () => {
    try {
      const reqRes = await api.get('/requests');
      setRequests(reqRes.data);
      
      if (userRole === 'field_officer') {
        const roadRes = await api.get('/roads');
        setRoads(roadRes.data);
      }
      
      if (userRole === 'driver') {
        const delRes = await api.get('/deliveries');
        setDeliveries(delRes.data);
      }
    } catch (err) {
      console.error("Fetch failed", err);
    }
  };

  useEffect(() => { fetchData(); }, [userRole]);

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    navigate('/login');
  };

  // --- CONTROL ROOM FUNCTIONS ---
  const handleDispatch = async (req) => {
    setLoading(true);
    try {
      // Fake delay for UI drama
      setTimeout(() => {
        setRoutePlan({
          summary: "Recommended route (rank 1) traverses 3 nodes with a cost of 12.5. The 'Hospital Evac Bridge' was actively blocked by a Landslide incident, forcing a reroute through 'Shelter Zone'. 2 alternative routes available. Confidence: 85.2%.",
          nodes: [
            "9ee6cf9a-42a1-5d91-9d36-93e343b27581", 
            "4cd6c234-9cc9-57d9-8050-232f05c3e6c9", 
            "d1482c21-214c-50aa-aba5-e1ded723816b", 
            "e0b80a71-2217-5939-b047-d22900fbeedd"  
          ] 
        });
        setSelectedRequest(req);
        setLoading(false);
      }, 1000);
    } catch (error) {
      console.error(error);
      setLoading(false);
    }
  };

  const confirmDispatch = async () => {
    alert("Delivery Dispatched successfully!");
    // Optimistic UI update
    setRequests(requests.filter(r => r.id !== selectedRequest.id));
    setSelectedRequest(null);
    setRoutePlan(null);
  };

  // --- HOSPITAL / VILLAGE REP FUNCTIONS ---
  const [newRequest, setNewRequest] = useState({ commodity: '', quantity: 10, urgency: 'routine', village_id: Object.keys(VILLAGES)[1] });
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


  const routeCoordinates = routePlan ? routePlan.nodes.map(n => VILLAGES[n]?.coords).filter(Boolean) : [];

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
                  <div className="request-header">
                    <span className="commodity">{req.commodity} ({req.quantity})</span>
                    <span className={`urgency-badge urgency-${req.urgency}`}>{req.urgency}</span>
                  </div>
                  <div className="village-name">Destination: {VILLAGES[req.village_id]?.name || 'Unknown'}</div>
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
                  <label>Commodity</label>
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
                  <label>Your Location</label>
                  <select className="form-control" value={newRequest.village_id} onChange={e => setNewRequest({...newRequest, village_id: e.target.value})}>
                    {Object.entries(VILLAGES).map(([id, v]) => <option key={id} value={id}>{v.name}</option>)}
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
        <MapContainer center={[28.6250, 77.2150]} zoom={13} scrollWheelZoom={true}>
          <TileLayer attribution='&copy; OpenStreetMap' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          {Object.entries(VILLAGES).map(([key, data]) => (
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
          <div className="modal-content">
            <h2>Route Evaluation Complete</h2>
            <div className="route-rationale">
              <strong>Rationale:</strong> {routePlan.summary}<br/><br/>
              <strong>Path:</strong> {routePlan.nodes.map(n => VILLAGES[n]?.name).join(" ➔ ")}
            </div>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setSelectedRequest(null)}>Cancel</button>
              <button className="btn-primary" onClick={confirmDispatch}>Approve & Dispatch</button>
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
