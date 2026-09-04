from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from uuid import UUID
from datetime import datetime

# --- Auth ---
class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    user_id: UUID

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str
    district: Optional[str] = None

class UserResponse(BaseModel):
    id: UUID
    name: str
    role: str
    district: Optional[str] = None
    email: str

    class Config:
        from_attributes = True

# --- Supply Requests ---
class SupplyRequestBase(BaseModel):
    village_id: UUID
    requester_id: Optional[UUID] = None
    commodity_category: str = "General"
    commodity: str
    quantity: int
    urgency: str = "routine"
    stockout_days: int = 0

class SupplyRequestCreate(SupplyRequestBase):
    pass

class SupplyRequestResponse(SupplyRequestBase):
    id: UUID
    priority_score: float
    priority_breakdown: Optional[Dict[str, Any]] = None
    is_overridden: bool = False
    override_reason: Optional[str] = None
    status: str
    fulfilled_quantity: int = 0
    parent_request_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PriorityOverrideRequest(BaseModel):
    new_score: float
    override_reason: str = Field(..., min_length=15)

# --- Incidents ---
class IncidentBase(BaseModel):
    road_segment_id: UUID
    reporter_id: UUID
    incident_type: str
    severity: str
    description: Optional[str] = None
    evidence_url: Optional[str] = None
    
class IncidentCreate(IncidentBase):
    pass

class IncidentResponse(IncidentBase):
    id: UUID
    confidence_score: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class IncidentVerifyRequest(BaseModel):
    verified_state: str
    verification_note: str

# --- Routing Engine Additions ---
class VehicleConstraints(BaseModel):
    weight_kg: Optional[float] = None
    height_m: Optional[float] = None
    is_hazmat: bool = False

class PolicyWeights(BaseModel):
    delay: float = 1.0
    risk: float = 1.0
    failure: float = 1.0
    resource: float = 1.0

class RouteEvaluationRequest(BaseModel):
    source_village_id: UUID
    target_village_id: UUID
    vehicle_constraints: Optional[VehicleConstraints] = Field(default_factory=VehicleConstraints)
    policy_weights: Optional[PolicyWeights] = Field(default_factory=PolicyWeights)

class RouteEvaluationResponse(BaseModel):
    feasible: bool
    summary: str
    constraints_applied: List[Dict[str, Any]]
    recommendation: Optional[Dict[str, Any]]
    alternatives: List[Dict[str, Any]]

# --- Deliveries (Dispatch & Proof of Delivery) ---
class DeliveryBase(BaseModel):
    supply_request_id: UUID
    driver_id: UUID
    route_plan: Dict[str, Any]

class DeliveryCreate(DeliveryBase):
    dispatched_quantity: Optional[int] = None

class DeliveryResponse(BaseModel):
    id: UUID
    supply_request_id: UUID
    driver_id: UUID
    status: str
    
    dispatched_quantity: int
    received_quantity: Optional[int] = None
    condition_status: Optional[str] = None
    discrepancy_reason: Optional[str] = None
    receiver_name: Optional[str] = None
    receiver_contact: Optional[str] = None
    pod_evidence_url: Optional[str] = None
    
    pod_notes: Optional[str] = None
    route_plan: Dict[str, Any] # Full rationale and path chosen
    created_at: datetime
    delivered_at: Optional[datetime] = None
    last_known_lat: Optional[float] = None
    last_known_lng: Optional[float] = None
    last_ping_at: Optional[datetime] = None
    deviation_status: Optional[str] = None

    class Config:
        from_attributes = True

class ProofOfDelivery(BaseModel):
    received_quantity: int
    condition_status: str
    discrepancy_reason: Optional[str] = None
    receiver_name: Optional[str] = None
    receiver_contact: Optional[str] = None
    pod_notes: Optional[str] = None

class TelemetryCreate(BaseModel):
    source_type: str
    latitude: float
    longitude: float
    speed_kmh: Optional[float] = None
    battery_level: Optional[int] = Field(None, ge=0, le=100)
    checkpoint_name: Optional[str] = None
    captured_at: Optional[datetime] = None

class TelemetryResponse(TelemetryCreate):
    id: UUID
    delivery_id: UUID
    server_received_at: datetime
    class Config:
        from_attributes = True

# --- Event Log ---
class EventLogCreate(BaseModel):
    event_type: str
    actor_id: Optional[UUID] = None
    correlation_id: Optional[UUID] = None
    payload: Dict[str, Any]

# --- Geospatial Entities ---
class VillageResponse(BaseModel):
    id: UUID
    name: str
    district: str
    population: Optional[int] = None
    isolation_score: Optional[float] = None
    coords: List[float]

    class Config:
        from_attributes = True

class RoadSegmentResponse(BaseModel):
    id: UUID
    name: Optional[str] = None
    source_id: UUID
    target_id: UUID
    accessibility_state: str
    distance_km: float
    base_travel_time_min: float
    risk_level: float
    failure_probability: float
    resource_cost: float
    road_type: str
    is_bridge: bool
    max_vehicle_weight_kg: Optional[float] = None
    max_vehicle_height_m: Optional[float] = None
    allows_hazmat: bool
    last_updated: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- EPIC-07: Offline Sync ---

class SyncActionItem(BaseModel):
    client_action_id: UUID
    action_type: str   # 'incident.create' | 'telemetry.create' | 'delivery.pod'
    entity_type: str   # 'incident' | 'telemetry' | 'delivery'
    payload: Dict[str, Any]
    occurred_at: Optional[datetime] = None  # client-captured timestamp

class SyncBatchRequest(BaseModel):
    client_id: UUID           # stable device/browser ID
    sync_batch_id: UUID       # unique ID for this specific batch attempt
    actions: List[SyncActionItem] = Field(..., max_length=50)  # cap batch size

class SyncActionResult(BaseModel):
    client_action_id: UUID
    status: str               # accepted | duplicate | rejected | conflict | validation_failed | authorization_failed
    server_entity_id: Optional[UUID] = None
    detail: Optional[str] = None

class SyncBatchResponse(BaseModel):
    sync_batch_id: UUID
    processed_count: int
    results: List[SyncActionResult]
