"""
database.py — Append-only geospatial audit store.

Uses SQLAlchemy with SQLite for local development.
Replace the SQLALCHEMY_DATABASE_URL with a PostgreSQL/PostGIS connection
string in production.

Schema normalised to BCNF:
  - Every non-key column is functionally dependent only on the full primary key.
  - No transitive dependencies.

Tables:
  nodes          — Intersection / location vertices (lat, lng).
  edges          — Directed road segments between nodes.
  incident_log   — Append-only audit history of every incident payload received.
  route_audit    — Append-only log of every routing decision made.
"""

import json
import os
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Boolean,
    create_engine,
    event,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# ---------------------------------------------------------------------------
# Engine & session
# ---------------------------------------------------------------------------
_db_path = os.environ.get("SQLITE_DB_PATH", "./test_router.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_db_path}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite-specific
)

# Enable WAL mode and foreign keys for SQLite (better concurrent read perf).
@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# ---------------------------------------------------------------------------
# Geospatial relational tables (BCNF)
# ---------------------------------------------------------------------------
class NodeRow(Base):
    """Graph vertex — an intersection or point of interest."""

    __tablename__ = "nodes"

    node_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # relationships
    outgoing_edges = relationship(
        "EdgeRow", foreign_keys="EdgeRow.source_node_id", back_populates="source_node"
    )
    incoming_edges = relationship(
        "EdgeRow", foreign_keys="EdgeRow.target_node_id", back_populates="target_node"
    )


class EdgeRow(Base):
    """Directed road segment between two nodes."""

    __tablename__ = "edges"

    edge_id = Column(String, primary_key=True)
    source_node_id = Column(
        String, ForeignKey("nodes.node_id"), nullable=False, index=True
    )
    target_node_id = Column(
        String, ForeignKey("nodes.node_id"), nullable=False, index=True
    )
    distance_km = Column(Float, nullable=False)
    base_travel_time_min = Column(Float, nullable=False)
    risk_level = Column(Float, nullable=False, default=0.0)  # 0.0–1.0
    failure_probability = Column(Float, nullable=False, default=0.0)  # 0.0–1.0
    resource_cost = Column(Float, nullable=False, default=0.0)
    road_type = Column(String, nullable=False, default="primary")
    is_bridge = Column(Boolean, nullable=False, default=False)
    max_vehicle_weight_kg = Column(Float, nullable=True)  # None = unrestricted
    max_vehicle_height_m = Column(Float, nullable=True)
    allows_hazmat = Column(Boolean, nullable=False, default=True)

    source_node = relationship(
        "NodeRow", foreign_keys=[source_node_id], back_populates="outgoing_edges"
    )
    target_node = relationship(
        "NodeRow", foreign_keys=[target_node_id], back_populates="incoming_edges"
    )


# ---------------------------------------------------------------------------
# Append-only audit tables
# ---------------------------------------------------------------------------
class IncidentLogRow(Base):
    """
    Append-only record of every incident payload received by the system.
    Rows are never updated or deleted — this is the audit trail.
    """

    __tablename__ = "incident_log"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # --- Canonical event envelope fields ---
    event_id = Column(String, nullable=False, unique=True, index=True)
    event_type = Column(String, nullable=False)
    occurred_at = Column(DateTime, nullable=False)
    received_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    source = Column(String, nullable=False)
    version = Column(String, nullable=False, default="1.0")

    # Full incident payload stored as JSON text for auditability.
    payload_json = Column(Text, nullable=False)


class RouteAuditRow(Base):
    """
    Append-only record of every routing decision made by the system.
    Links back to the incident that triggered it.
    """

    __tablename__ = "route_audit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, nullable=False, index=True)
    computed_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    source_node_id = Column(String, nullable=False)
    target_node_id = Column(String, nullable=False)
    k_requested = Column(Integer, nullable=False)
    best_route_cost = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    result_json = Column(Text, nullable=False)  # full response payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def init_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a session, ensures close."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def persist_incident(db, incident_dict: dict) -> IncidentLogRow:
    """Write an incident to the append-only log. Returns the created row."""
    row = IncidentLogRow(
        event_id=incident_dict["event_id"],
        event_type=incident_dict["event_type"],
        occurred_at=incident_dict["occurred_at"],
        source=incident_dict["source"],
        version=incident_dict.get("version", "1.0"),
        payload_json=json.dumps(incident_dict, default=str),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def persist_route_audit(db, event_id: str, source: str, target: str,
                        k: int, best_cost: float | None,
                        confidence: float | None, result: dict) -> RouteAuditRow:
    """Write a routing decision to the append-only audit log."""
    row = RouteAuditRow(
        event_id=event_id,
        source_node_id=source,
        target_node_id=target,
        k_requested=k,
        best_route_cost=best_cost,
        confidence_score=confidence,
        result_json=json.dumps(result, default=str),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def load_nodes(db) -> list[NodeRow]:
    """Load all nodes from the database."""
    return db.query(NodeRow).all()


def load_edges(db) -> list[EdgeRow]:
    """Load all edges from the database."""
    return db.query(EdgeRow).all()


def seed_demo_graph(db) -> None:
    """
    Seed a small demo graph for local testing.
    Only inserts if the nodes table is empty.
    """
    if db.query(NodeRow).first() is not None:
        return

    nodes = [
        NodeRow(node_id="N1", name="Base Camp Alpha", latitude=28.6139, longitude=77.2090),
        NodeRow(node_id="N2", name="Field Hospital", latitude=28.6200, longitude=77.2150),
        NodeRow(node_id="N3", name="Supply Depot", latitude=28.6280, longitude=77.2050),
        NodeRow(node_id="N4", name="Evacuation Point", latitude=28.6350, longitude=77.2200),
        NodeRow(node_id="N5", name="Shelter Zone", latitude=28.6100, longitude=77.2300),
        NodeRow(node_id="N6", name="Command Center", latitude=28.6400, longitude=77.2100),
    ]

    edges = [
        # N1 → N2 (direct, short)
        EdgeRow(edge_id="E1", source_node_id="N1", target_node_id="N2",
                distance_km=1.2, base_travel_time_min=4.0, risk_level=0.1,
                failure_probability=0.05, resource_cost=10.0, road_type="primary",
                is_bridge=False, allows_hazmat=True),
        # N1 → N3 (medium, low risk)
        EdgeRow(edge_id="E2", source_node_id="N1", target_node_id="N3",
                distance_km=2.5, base_travel_time_min=8.0, risk_level=0.05,
                failure_probability=0.02, resource_cost=15.0, road_type="primary",
                is_bridge=False, allows_hazmat=True),
        # N2 → N4 (bridge crossing)
        EdgeRow(edge_id="E3", source_node_id="N2", target_node_id="N4",
                distance_km=2.0, base_travel_time_min=6.0, risk_level=0.3,
                failure_probability=0.15, resource_cost=20.0, road_type="secondary",
                is_bridge=True, max_vehicle_weight_kg=10000.0, allows_hazmat=False),
        # N3 → N4 (alternative to bridge)
        EdgeRow(edge_id="E4", source_node_id="N3", target_node_id="N4",
                distance_km=3.0, base_travel_time_min=10.0, risk_level=0.15,
                failure_probability=0.08, resource_cost=25.0, road_type="primary",
                is_bridge=False, allows_hazmat=True),
        # N2 → N5 (short connector)
        EdgeRow(edge_id="E5", source_node_id="N2", target_node_id="N5",
                distance_km=1.8, base_travel_time_min=5.0, risk_level=0.2,
                failure_probability=0.10, resource_cost=12.0, road_type="secondary",
                is_bridge=False, allows_hazmat=True),
        # N5 → N4 (longer alternate)
        EdgeRow(edge_id="E6", source_node_id="N5", target_node_id="N4",
                distance_km=3.5, base_travel_time_min=12.0, risk_level=0.25,
                failure_probability=0.12, resource_cost=30.0, road_type="tertiary",
                is_bridge=False, max_vehicle_weight_kg=5000.0, allows_hazmat=True),
        # N3 → N6 (supply route)
        EdgeRow(edge_id="E7", source_node_id="N3", target_node_id="N6",
                distance_km=2.2, base_travel_time_min=7.0, risk_level=0.10,
                failure_probability=0.03, resource_cost=18.0, road_type="primary",
                is_bridge=False, allows_hazmat=True),
        # N6 → N4 (command to evac)
        EdgeRow(edge_id="E8", source_node_id="N6", target_node_id="N4",
                distance_km=1.5, base_travel_time_min=5.0, risk_level=0.20,
                failure_probability=0.07, resource_cost=22.0, road_type="secondary",
                is_bridge=True, max_vehicle_weight_kg=15000.0, allows_hazmat=True),
    ]

    db.add_all(nodes)
    db.add_all(edges)
    db.commit()
