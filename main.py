"""
main.py — FastAPI microservice for emergency logistics routing.

Pipeline on POST /route:
  1. Persist incident to append-only audit log (database.py)
  2. Load graph from DB → prune hard constraints → apply policy weights
  3. Run Yen's K-Shortest Paths (graph_engine.py)
  4. Persist routing decision to audit log
  5. Return explainable response with confidence, rationale, and timestamps
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import (
    get_db,
    init_db,
    load_edges,
    load_nodes,
    persist_incident,
    persist_route_audit,
    seed_demo_graph,
    SessionLocal,
)
from graph_engine import (
    apply_policy_weights,
    build_graph,
    build_rationale,
    compute_confidence,
    find_k_shortest_paths,
    prune_graph,
)

# ───────────────────────────────────────────────────────────────────────
# Pydantic models
# ───────────────────────────────────────────────────────────────────────


class VehicleConstraints(BaseModel):
    """Physical constraints of the delivery vehicle."""
    weight_kg: Optional[float] = Field(None, description="Vehicle gross weight in kg")
    height_m: Optional[float] = Field(None, description="Vehicle height in metres")
    is_hazmat: bool = Field(False, description="Carrying hazardous materials")


class PolicyWeights(BaseModel):
    """Tuneable multipliers for the four cost components."""
    delay: float = Field(1.0, ge=0.0, description="Weight for travel delay cost")
    risk: float = Field(1.0, ge=0.0, description="Weight for route risk cost")
    failure: float = Field(1.0, ge=0.0, description="Weight for failure cost")
    resource: float = Field(1.0, ge=0.0, description="Weight for resource cost")


class IncidentPayload(BaseModel):
    """
    Canonical event envelope for an incident.

    Every field here maps 1-to-1 into the append-only incident_log table.
    """
    event_id: str = Field(..., description="Globally unique event identifier")
    event_type: str = Field(
        ..., description="Event classification (e.g. 'flood', 'earthquake', 'road_closure')"
    )
    occurred_at: datetime = Field(..., description="When the incident occurred (ISO 8601)")
    source: str = Field(
        ..., description="Originating system or authority (e.g. 'NDMA', 'field_officer')"
    )
    version: str = Field("1.0", description="Schema version of this envelope")

    # Single-edge incident fields (flat format)
    edge_id: Optional[str] = Field(None, description="Affected edge ID")
    status: Optional[str] = Field(None, description="Edge status (e.g. 'blocked', 'hazardous')")
    hazard_type: Optional[str] = Field(None, description="Type of hazard (e.g. 'flood', 'landslide_risk')")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence in this report")

    # Batch constraint lists (explicit format)
    closed_edge_ids: list[str] = Field(
        default_factory=list, description="Edge IDs that are actively closed"
    )
    unavailable_bridges: list[str] = Field(
        default_factory=list, description="Bridge edge IDs that are damaged/unavailable"
    )


class RouteRequest(BaseModel):
    """Full request body for POST /route."""
    incident: IncidentPayload
    source_node: str = Field(..., description="Starting node ID")
    target_node: str = Field(..., description="Destination node ID")
    k: int = Field(3, ge=1, le=10, description="Number of alternative routes")
    vehicle: VehicleConstraints = Field(default_factory=VehicleConstraints)
    policy_weights: PolicyWeights = Field(default_factory=PolicyWeights)


class CostBreakdown(BaseModel):
    travel_delay_cost: float
    route_risk_cost: float
    failure_cost: float
    resource_cost: float
    total: float


class EdgeDetail(BaseModel):
    edge_id: str
    from_node: str = Field(..., alias="from")
    to_node: str = Field(..., alias="to")
    cost_breakdown: CostBreakdown

    model_config = {"populate_by_name": True}


class PathResult(BaseModel):
    rank: int
    nodes: list[str]
    total_cost: float
    edge_details: list[EdgeDetail]


class ConstraintApplied(BaseModel):
    edge: str
    reason: str


class Recommendation(BaseModel):
    route: PathResult
    confidence: float
    reason: str


class Rationale(BaseModel):
    summary: str
    constraints_applied: list[ConstraintApplied]
    recommendation: Optional[Recommendation] = None
    alternatives: list[PathResult] = Field(default_factory=list)


class RouteResponse(BaseModel):
    """Explainable API response."""
    event_id: str
    computed_at: datetime
    data_freshness: datetime = Field(
        ..., description="Timestamp of graph data used for this computation"
    )
    source_node: str
    target_node: str
    k_requested: int
    paths: list[PathResult]
    confidence_score: float
    rationale: Rationale


# ───────────────────────────────────────────────────────────────────────
# Application
# ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="GIS Emergency Router",
    description=(
        "Deterministic, explainable routing API for emergency deliveries "
        "in disaster zones. No ML — constraint pruning + policy-weighted "
        "Yen's K-Shortest Paths."
    ),
    version="0.1.0",
)


@app.on_event("startup")
def startup() -> None:
    """Initialise database and seed demo graph on first run."""
    init_db()
    db = SessionLocal()
    try:
        seed_demo_graph(db)
    finally:
        db.close()


# ───────────────────────────────────────────────────────────────────────
# Endpoints
# ───────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/route", response_model=RouteResponse)
def compute_route(req: RouteRequest, db: Session = Depends(get_db)):
    """
    Full routing pipeline:
      1. Persist incident → append-only audit log
      2. Build graph from DB
      3. Prune hard constraints
      4. Apply policy weights
      5. Run Yen's K-Shortest Paths
      6. Persist routing decision → audit log
      7. Return explainable response
    """
    now = datetime.now(timezone.utc)

    # ── Step 1: Persist incident ──────────────────────────────────────
    persist_incident(db, req.incident.model_dump())

    # ── Step 2: Build graph from current DB state ─────────────────────
    nodes = load_nodes(db)
    edges = load_edges(db)

    if not nodes:
        raise HTTPException(status_code=503, detail="No graph data in database")

    graph = build_graph(nodes, edges)

    # ── Step 3: Hard constraint pruning ───────────────────────────────
    # Merge explicit lists with single-edge incident fields
    closed = set(req.incident.closed_edge_ids)
    bridges = set(req.incident.unavailable_bridges)

    if req.incident.edge_id and req.incident.status in ("blocked", "closed"):
        closed.add(req.incident.edge_id)
    if req.incident.edge_id and req.incident.hazard_type == "bridge_failure":
        bridges.add(req.incident.edge_id)

    pruned, pruned_log = prune_graph(
        graph=graph,
        closed_edge_ids=closed,
        unavailable_bridges=bridges,
        vehicle_weight_kg=req.vehicle.weight_kg,
        vehicle_height_m=req.vehicle.height_m,
        is_hazmat=req.vehicle.is_hazmat,
    )

    # ── Step 4: Dynamic policy weighting ──────────────────────────────
    weighted = apply_policy_weights(
        pruned,
        w_delay=req.policy_weights.delay,
        w_risk=req.policy_weights.risk,
        w_failure=req.policy_weights.failure,
        w_resource=req.policy_weights.resource,
    )

    # ── Step 5: Yen's K-Shortest Paths ───────────────────────────────
    paths = find_k_shortest_paths(weighted, req.source_node, req.target_node, k=req.k)
    confidence = compute_confidence(paths)

    # ── Step 6: Build rationale ───────────────────────────────────────
    rationale = build_rationale(paths, pruned_log, confidence)

    # ── Step 7: Persist routing decision ──────────────────────────────
    best_cost = paths[0]["total_cost"] if paths else None
    result_payload = {
        "paths": paths,
        "confidence": confidence,
        "rationale": rationale,
    }
    persist_route_audit(
        db,
        event_id=req.incident.event_id,
        source=req.source_node,
        target=req.target_node,
        k=req.k,
        best_cost=best_cost,
        confidence=confidence,
        result=result_payload,
    )

    # ── Step 8: Assemble response ─────────────────────────────────────
    return RouteResponse(
        event_id=req.incident.event_id,
        computed_at=now,
        data_freshness=now,
        source_node=req.source_node,
        target_node=req.target_node,
        k_requested=req.k,
        paths=paths,
        confidence_score=confidence,
        rationale=rationale,
    )
