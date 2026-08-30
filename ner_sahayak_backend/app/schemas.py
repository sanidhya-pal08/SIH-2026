from pydantic import BaseModel
from typing import Optional, Any, Dict
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
    phone_number: str
    password: str
    role: str
    district: Optional[str] = None

class UserResponse(BaseModel):
    id: UUID
    name: str
    role: str
    district: Optional[str] = None
    phone_number: str

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

# --- Incidents (Field Reports / Disruptions) ---
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

# --- Deliveries (Dispatch & Proof of Delivery) ---
class DeliveryBase(BaseModel):
    supply_request_id: UUID
    driver_id: UUID
    route_plan: Dict[str, Any] # Contains the route coordinates and risk explanation

class DeliveryCreate(DeliveryBase):
    pass

class DeliveryResponse(DeliveryBase):
    id: UUID
    status: str
    pod_notes: Optional[str] = None
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
