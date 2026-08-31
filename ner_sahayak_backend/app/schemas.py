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
    commodity: str
    quantity: int
    urgency: str = "routine"

class SupplyRequestCreate(SupplyRequestBase):
    pass

class SupplyRequestResponse(SupplyRequestBase):
    id: UUID
    priority_score: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

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

# --- Deliveries (Dispatch & Proof of Delivery) ---
class DeliveryBase(BaseModel):
    supply_request_id: UUID
    driver_id: UUID
    # Instead of raw route_plan payload, we calculate it dynamically
    vehicle_constraints: Optional[VehicleConstraints] = Field(default_factory=VehicleConstraints)
    policy_weights: Optional[PolicyWeights] = Field(default_factory=PolicyWeights)

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
