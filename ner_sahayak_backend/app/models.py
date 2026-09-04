import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False)
    district = Column(String(100))
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class RoadSegment(Base):
    __tablename__ = "road_segments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255))
    source_id = Column(UUID(as_uuid=True), ForeignKey('villages.id'))
    target_id = Column(UUID(as_uuid=True), ForeignKey('villages.id'))
    geom = Column(Geometry('LINESTRING', srid=4326))
    accessibility_state = Column(String(50), default='open') # open, restricted, hazardous, blocked
    distance_km = Column(Float, nullable=False, default=1.0)
    base_travel_time_min = Column(Float, nullable=False, default=5.0)
    risk_level = Column(Float, nullable=False, default=0.0)
    failure_probability = Column(Float, nullable=False, default=0.0)
    resource_cost = Column(Float, nullable=False, default=0.0)
    road_type = Column(String(50), nullable=False, default="primary")
    is_bridge = Column(Boolean, nullable=False, default=False)
    max_vehicle_weight_kg = Column(Float, nullable=True)
    max_vehicle_height_m = Column(Float, nullable=True)
    allows_hazmat = Column(Boolean, nullable=False, default=True)
    last_updated = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    disruption_probability = Column(Float, nullable=True)
    predicted_risk_band = Column(String(50), nullable=True)
    risk_factors = Column(JSON, nullable=True)

class SegmentFeature(Base):
    __tablename__ = "segment_features"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    road_segment_id = Column(UUID(as_uuid=True), ForeignKey('road_segments.id'))
    features_json = Column(JSON, nullable=False)
    captured_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class Village(Base):
    __tablename__ = "villages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    district = Column(String(100), nullable=False)
    geom = Column(Geometry('POINT', srid=4326))
    population = Column(Integer)
    isolation_score = Column(Float, default=0.0)
    is_handoff = Column(Boolean, default=False)

class Incident(Base):
    __tablename__ = "incidents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    road_segment_id = Column(UUID(as_uuid=True), ForeignKey('road_segments.id'))
    reporter_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    incident_type = Column(String(50))
    severity = Column(String(50))
    description = Column(String)
    geom = Column(Geometry('POINT', srid=4326))
    evidence_url = Column(String)
    confidence_score = Column(Float, default=1.0)
    status = Column(String(50), default='pending_review')
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class SupplyRequest(Base):
    __tablename__ = "supply_requests"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_id = Column(UUID(as_uuid=True), ForeignKey('villages.id'))
    requester_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    commodity_category = Column(String(50), nullable=False, default='General')
    commodity = Column(String(100), nullable=False)
    quantity = Column(Integer, nullable=False)
    fulfilled_quantity = Column(Integer, nullable=False, default=0)
    urgency = Column(String(50), default='routine')
    stockout_days = Column(Integer, nullable=False, default=0)
    priority_score = Column(Float, default=0.0)
    priority_breakdown = Column(JSON)
    is_overridden = Column(Boolean, default=False)
    override_reason = Column(String)
    status = Column(String(50), default='open')
    parent_request_id = Column(UUID(as_uuid=True), ForeignKey('supply_requests.id'), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class Delivery(Base):
    __tablename__ = "deliveries"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supply_request_id = Column(UUID(as_uuid=True), ForeignKey('supply_requests.id'))
    driver_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    route_plan = Column(JSON)
    status = Column(String(50), default='dispatched')
    
    # EPIC-08 Fields
    dispatched_quantity = Column(Integer, nullable=False, default=0)
    received_quantity = Column(Integer, nullable=True)
    condition_status = Column(String(50), nullable=True)
    discrepancy_reason = Column(String, nullable=True)
    receiver_name = Column(String(100), nullable=True)
    receiver_contact = Column(String(100), nullable=True)
    pod_evidence_url = Column(String, nullable=True)
    
    pod_notes = Column(String)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    delivered_at = Column(DateTime(timezone=True))
    last_known_lat = Column(Float, nullable=True)
    last_known_lng = Column(Float, nullable=True)
    last_ping_at = Column(DateTime(timezone=True), nullable=True)
    deviation_status = Column(String(50), default='normal')

class DeliveryTelemetry(Base):
    __tablename__ = "delivery_telemetry"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    delivery_id = Column(UUID(as_uuid=True), ForeignKey('deliveries.id'))
    source_type = Column(String(50))
    latitude = Column(Float)
    longitude = Column(Float)
    geom = Column(Geometry('POINT', srid=4326))
    speed_kmh = Column(Float, nullable=True)
    battery_level = Column(Integer, nullable=True)
    checkpoint_name = Column(String, nullable=True)
    captured_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    server_received_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class EventLog(Base):
    __tablename__ = "event_log"
    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(100), nullable=False)
    actor_id = Column(UUID(as_uuid=True))
    correlation_id = Column(UUID(as_uuid=True))
    payload = Column(JSON, nullable=False)
    checksum = Column(String(64), nullable=True)
    previous_hash = Column(String(64), nullable=True)
    occurred_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    received_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class ProcessedSyncAction(Base):
    """Server-side idempotency ledger for offline sync actions."""
    __tablename__ = "processed_sync_actions"
    # client_action_id is the idempotency key — unique constraint prevents duplicate processing
    client_action_id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    action_type = Column(String(100), nullable=False)
    result_status = Column(String(50), nullable=False)  # accepted, duplicate, rejected, conflict, validation_failed
    server_entity_id = Column(UUID(as_uuid=True), nullable=True)  # ID of the created server entity
    occurred_at = Column(DateTime(timezone=True), nullable=True)   # client-captured time
    processed_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String(100), nullable=False)
    severity = Column(String(50), nullable=False)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    related_request_id = Column(UUID(as_uuid=True), ForeignKey('supply_requests.id'), nullable=True)
    related_delivery_id = Column(UUID(as_uuid=True), ForeignKey('deliveries.id'), nullable=True)
    status = Column(String(50), default="active") # active, acknowledged, resolved
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    recommendation_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class AirEscalation(Base):
    __tablename__ = "air_escalations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), ForeignKey('supply_requests.id'), nullable=False)
    approved_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    reason = Column(String, nullable=False)
    decision = Column(String(50), nullable=False) # approved, rejected
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

