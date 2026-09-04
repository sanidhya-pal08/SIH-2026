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
    requester_id: UUID
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
    pass

class DeliveryResponse(BaseModel):
    id: UUID
    supply_request_id: UUID
    driver_id: UUID
    status: str
    pod_notes: Optional[str] = None
    route_plan: Dict[str, Any] # Full rationale and path chosen
    created_at: datetime
    delivered_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ProofOfDelivery(BaseModel):
    pod_notes: str

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

