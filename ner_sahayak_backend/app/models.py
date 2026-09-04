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

class Village(Base):
    __tablename__ = "villages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    district = Column(String(100), nullable=False)
    geom = Column(Geometry('POINT', srid=4326))
    population = Column(Integer)
    isolation_score = Column(Float, default=0.0)

class Incident(Base):
    __tablename__ = "incidents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    road_segment_id = Column(UUID(as_uuid=True), ForeignKey('road_segments.id'))
    reporter_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    incident_type = Column(String(50))
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
    urgency = Column(String(50), default='routine')
    stockout_days = Column(Integer, nullable=False, default=0)
    priority_score = Column(Float, default=0.0)
    priority_breakdown = Column(JSON)
    is_overridden = Column(Boolean, default=False)
    override_reason = Column(String)
    status = Column(String(50), default='open')
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class Delivery(Base):
    __tablename__ = "deliveries"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supply_request_id = Column(UUID(as_uuid=True), ForeignKey('supply_requests.id'))
    driver_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    route_plan = Column(JSON)
    status = Column(String(50), default='dispatched')
    pod_notes = Column(String)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    delivered_at = Column(DateTime(timezone=True))

class EventLog(Base):
    __tablename__ = "event_log"
    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(100), nullable=False)
    actor_id = Column(UUID(as_uuid=True))
    correlation_id = Column(UUID(as_uuid=True))
    payload = Column(JSON, nullable=False)
    occurred_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    received_at = Column(DateTime(timezone=True), default=datetime.utcnow)
