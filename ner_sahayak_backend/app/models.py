import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    district = Column(String(100))
    phone_number = Column(String(20), unique=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class RoadSegment(Base):
    __tablename__ = "road_segments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255))
    geom = Column(Geometry('LINESTRING', srid=4326))
    accessibility_state = Column(String(50), default='open')
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
    commodity = Column(String(100), nullable=False)
    quantity = Column(Integer, nullable=False)
    urgency = Column(String(50), default='routine')
    priority_score = Column(Float, default=0.0)
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
