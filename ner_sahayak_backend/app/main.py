from fastapi import FastAPI, Depends, HTTPException, status, Request, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
import os
import uuid
from sqlalchemy.orm import Session
from fastapi.encoders import jsonable_encoder
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import json
from sqlalchemy import func

from . import models, schemas, auth, graph_engine, priority_engine, routing_service, environmental_service, prediction_service, delivery_service
from .database import engine, get_db, SessionLocal
from .seed import seed_demo_graph

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="NER Sahayak API",
    description="Core backend for NER Sahayak logistics platform with RBAC and GIS Routing",
    version="1.0.0"
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to the frontend URL
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup() -> None:
    # 1. Create tables in PostGIS (if they don't exist)
    models.Base.metadata.create_all(bind=engine)
    # 2. Connect and seed the database with Member 2's mock data
    db = SessionLocal()
    try:
        seed_demo_graph(db)
    finally:
        db.close()

allow_control_room = auth.RoleChecker(["control_room"])
allow_field_staff = auth.RoleChecker(["field_officer", "driver"])
allow_driver = auth.RoleChecker(["driver"])

@app.get("/")
def read_root():
    return {"message": "NER Sahayak API is running securely"}

@app.get("/api/v1/health")
def health_check():
    """Unauthenticated health ping — used by the frontend sync worker to probe connectivity."""
    return {"status": "ok"}

@app.post("/api/v1/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials")
    access_token = auth.create_access_token(data={"sub": str(user.id), "role": user.role})
    return {"access_token": access_token, "token_type": "bearer", "role": user.role, "user_id": user.id}

@app.post("/api/v1/auth/register", response_model=schemas.UserResponse)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = models.User(**user.model_dump(exclude={"password"}), hashed_password=auth.get_password_hash(user.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.get("/api/v1/users", response_model=List[schemas.UserResponse])
def get_users(role: Optional[str] = None, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    query = db.query(models.User)
    if role:
        query = query.filter(models.User.role == role)
    return query.all()

@app.post("/api/v1/requests", response_model=schemas.SupplyRequestResponse)
def create_supply_request(req: schemas.SupplyRequestCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    req_dict = req.model_dump()
    if not req_dict.get('requester_id'):
        req_dict['requester_id'] = current_user.id
    db_request = models.SupplyRequest(**req_dict)
    
    village = db.query(models.Village).filter(models.Village.id == req.village_id).first()
    pop = village.population if village else 0
    iso = village.isolation_score if village else 0.0

    score, breakdown = priority_engine.calculate_priority(
        urgency=req.urgency,
        category=req.commodity_category,
        population=pop,
        isolation=iso,
        stockout_days=req.stockout_days,
        local_supply=0
    )
    
    db_request.priority_score = score
    db_request.priority_breakdown = breakdown
    db.add(db_request)
    db.flush()

    db.add(models.EventLog(event_type="SupplyRequestCreated", actor_id=current_user.id, correlation_id=db_request.id, payload=jsonable_encoder(req)))
    db.commit()
    db.refresh(db_request)
    return db_request

@app.patch("/api/v1/requests/{request_id}/override", response_model=schemas.SupplyRequestResponse)
def override_supply_request(request_id: UUID, req: schemas.PriorityOverrideRequest, db: Session = Depends(get_db), current_user: models.User = Depends(allow_control_room)):
    db_req = db.query(models.SupplyRequest).filter(models.SupplyRequest.id == request_id).first()
    if not db_req:
        raise HTTPException(status_code=404, detail="Supply request not found")
    
    db_req.priority_score = req.new_score
    db_req.is_overridden = True
    db_req.override_reason = req.override_reason
    db.flush()

    db.add(models.EventLog(
        event_type="PriorityOverridden", 
        actor_id=current_user.id, 
        correlation_id=db_req.id, 
        payload={"new_score": req.new_score, "override_reason": req.override_reason}
    ))
    db.commit()
    db.refresh(db_req)
    return db_req

@app.get("/api/v1/requests", response_model=List[schemas.SupplyRequestResponse])
def list_supply_requests(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    query = db.query(models.SupplyRequest)
    if current_user.role != 'control_room':
        query = query.filter(models.SupplyRequest.requester_id == current_user.id)
    return query.order_by(models.SupplyRequest.priority_score.desc()).offset(skip).limit(limit).all()

@app.post("/api/v1/incidents", response_model=schemas.IncidentResponse)
def report_incident(
    road_segment_id: UUID = Form(...),
    incident_type: str = Form(...),
    severity: str = Form(...),
    description: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(allow_field_staff)
):
    evidence_url = None
    if photo and photo.filename:
        if photo.content_type not in ["image/jpeg", "image/png"]:
            raise HTTPException(status_code=400, detail="Invalid MIME type. Only JPEG and PNG are allowed.")
        file_bytes = photo.file.read()
        if len(file_bytes) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Max 5MB.")
        ext = photo.filename.split(".")[-1]
        safe_filename = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, safe_filename)
        with open(filepath, "wb") as f:
            f.write(file_bytes)
        evidence_url = f"/uploads/{safe_filename}"
        
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise HTTPException(status_code=400, detail="Invalid coordinates.")
        
    confidence_score = 0.9 if current_user.role == 'field_officer' else 0.7
    
    db_incident = models.Incident(
        road_segment_id=road_segment_id,
        reporter_id=current_user.id,
        incident_type=incident_type,
        severity=severity,
        description=description,
        evidence_url=evidence_url,
        confidence_score=confidence_score,
        geom=f"SRID=4326;POINT({longitude} {latitude})"
    )
    db.add(db_incident)
    db.flush()
    
    db.add(models.EventLog(
        event_type="IncidentReported", 
        actor_id=current_user.id, 
        correlation_id=db_incident.id, 
        payload={"incident_type": incident_type, "severity": severity}
    ))
    
    db_road = db.query(models.RoadSegment).filter(models.RoadSegment.id == road_segment_id).first()
    if db_road:
        active_incidents = db.query(models.Incident).filter(
            models.Incident.road_segment_id == road_segment_id,
            models.Incident.status == 'pending_review'
        ).all()
        
        def implied_state(inc_type, sev):
            if inc_type in ['reopened', 'open']:
                return 'open'
            if sev == 'critical':
                return 'blocked'
            return 'hazardous'
            
        states = set([implied_state(i.incident_type, i.severity) for i in active_incidents])
        
        if len(states) > 1:
            db_road.accessibility_state = 'disputed'
        else:
            new_implied = implied_state(incident_type, severity)
            if new_implied == 'blocked' and db_road.accessibility_state != 'blocked':
                db_road.accessibility_state = 'blocked'
            elif new_implied == 'open' and db_road.accessibility_state != 'open':
                db_road.accessibility_state = 'open'
                
        db_road.last_updated = datetime.utcnow()

    db.commit()
    db.refresh(db_incident)
    return db_incident

@app.post("/api/v1/incidents/{incident_id}/verify")
def verify_incident(
    incident_id: UUID,
    req: schemas.IncidentVerifyRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(allow_control_room)
):
    incident = db.query(models.Incident).filter(models.Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    if req.verified_state not in ['open', 'hazardous', 'restricted', 'blocked']:
        raise HTTPException(status_code=400, detail="Invalid verified state")
        
    incident.status = 'verified'
    
    db_road = db.query(models.RoadSegment).filter(models.RoadSegment.id == incident.road_segment_id).first()
    if db_road:
        db_road.accessibility_state = req.verified_state
        db_road.last_updated = datetime.utcnow()
        
        if req.verified_state == 'blocked':
            active_deliveries = db.query(models.Delivery).filter(models.Delivery.status == 'dispatched').all()
            for d in active_deliveries:
                route_plan = d.route_plan
                if route_plan and 'recommendation' in route_plan and route_plan['recommendation'] and 'route' in route_plan['recommendation']:
                    edges = route_plan['recommendation']['route'].get('edge_details', [])
                    edge_ids = [e.get('edge_id') for e in edges]
                    if str(db_road.id) in edge_ids:
                        d.status = 'requires_reroute'
                        db_req = db.query(models.SupplyRequest).filter(models.SupplyRequest.id == d.supply_request_id).first()
                        if db_req:
                            db_req.status = 'open'
                        
    db.add(models.EventLog(
        event_type="ConflictVerified",
        actor_id=current_user.id,
        correlation_id=incident.id,
        payload={"verified_state": req.verified_state, "note": req.verification_note}
    ))
    db.commit()
    return {"status": "success", "verified_state": req.verified_state}

@app.get("/api/v1/incidents", response_model=List[schemas.IncidentResponse])
def get_incidents(db: Session = Depends(get_db)):
    return db.query(models.Incident).all()

@app.get("/api/v1/deliveries/active", response_model=List[schemas.DeliveryResponse])
def get_active_deliveries(db: Session = Depends(get_db), current_user: models.User = Depends(allow_control_room)):
    return db.query(models.Delivery).filter(
        models.Delivery.status.in_(['dispatched', 'requires_reroute'])
    ).all()

@app.post("/api/v1/deliveries/{delivery_id}/telemetry", response_model=schemas.TelemetryResponse)
def submit_telemetry(
    delivery_id: UUID,
    req: schemas.TelemetryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # Ensure delivery exists
    delivery = db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
        
    # Authorization: Must be control room OR assigned driver
    if current_user.role != 'control_room' and (current_user.role != 'driver' or delivery.driver_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to submit telemetry for this delivery")
        
    # Validation constraints
    if not (-90 <= req.latitude <= 90 and -180 <= req.longitude <= 180):
        raise HTTPException(status_code=400, detail="Invalid coordinates")
    if req.speed_kmh is not None and req.speed_kmh < 0:
        raise HTTPException(status_code=400, detail="Speed cannot be negative")
    if req.source_type == 'manual_checkpoint' and not req.checkpoint_name:
        raise HTTPException(status_code=400, detail="Manual checkpoints require a checkpoint name")
        
    captured = req.captured_at or datetime.utcnow()
    geom = f"SRID=4326;POINT({req.longitude} {req.latitude})"
    
    telemetry = models.DeliveryTelemetry(
        delivery_id=delivery_id,
        source_type=req.source_type,
        latitude=req.latitude,
        longitude=req.longitude,
        speed_kmh=req.speed_kmh,
        battery_level=req.battery_level,
        checkpoint_name=req.checkpoint_name,
        captured_at=captured,
        geom=geom
    )
    db.add(telemetry)
    
    delivery.last_known_lat = req.latitude
    delivery.last_known_lng = req.longitude
    delivery.last_ping_at = captured
    
    # Route Deviation Detection
    # If route_plan exists, get the edge IDs and query RoadSegment geometries
    is_deviated = False
    if delivery.route_plan and 'recommendation' in delivery.route_plan and delivery.route_plan['recommendation'] and 'route' in delivery.route_plan['recommendation']:
        edge_details = delivery.route_plan['recommendation']['route'].get('edge_details', [])
        edge_ids = [e.get('edge_id') for e in edge_details if e.get('edge_id')]
        
        if edge_ids:
            # We want to find the MIN distance from the telemetry point to ANY of these road segments.
            # Using PostGIS ST_Distance(geography, geography)
            from sqlalchemy import cast, func
            from geoalchemy2 import Geography
            
            point_geom = func.ST_SetSRID(func.ST_Point(req.longitude, req.latitude), 4326)
            
            min_dist = db.query(
                func.min(func.ST_Distance(cast(point_geom, Geography), cast(models.RoadSegment.geom, Geography)))
            ).filter(
                models.RoadSegment.id.in_(edge_ids)
            ).scalar()
            
            # If distance is > 2000 meters (2km), mark as deviated. Configurable.
            if min_dist is not None and min_dist > 2000.0:
                is_deviated = True
                
    if is_deviated and delivery.deviation_status != 'deviated':
        delivery.deviation_status = 'deviated'
        db.add(models.EventLog(
            event_type="RouteDeviationDetected",
            actor_id=current_user.id,
            correlation_id=delivery.id,
            payload={"latitude": req.latitude, "longitude": req.longitude, "distance_from_route": float(min_dist) if min_dist else None}
        ))
    elif not is_deviated and delivery.deviation_status == 'deviated':
        delivery.deviation_status = 'normal'
        
    db.add(models.EventLog(
        event_type="TelemetryReceived",
        actor_id=current_user.id,
        correlation_id=delivery.id,
        payload={"source_type": req.source_type, "latitude": req.latitude, "longitude": req.longitude}
    ))
    
    db.commit()
    db.refresh(telemetry)
    return telemetry

@app.post("/api/v1/routes/evaluate", response_model=schemas.RouteEvaluationResponse)
def evaluate_route(req: schemas.RouteEvaluationRequest, db: Session = Depends(get_db), current_user: models.User = Depends(allow_control_room)):
    rationale = routing_service.evaluate_routes(
        db=db,
        source_id=str(req.source_village_id),
        target_id=str(req.target_village_id),
        vehicle_constraints=req.vehicle_constraints,
        policy_weights=req.policy_weights
    )

    from . import audit_service, alert_service
    # Epic 10: Event Log
    audit_service.log_event(
        db=db,
        event_type="RouteEvaluated",
        payload={"source": str(req.source_village_id), "target": str(req.target_village_id), "feasible": rationale.get("feasible")},
        actor_id=current_user.id,
        correlation_id=req.request_id
    )

    # Epic 09: Alert if cut off
    if not rationale.get("feasible") and req.request_id:
        req_db = db.query(models.SupplyRequest).filter(models.SupplyRequest.id == req.request_id).first()
        if req_db and (req_db.urgency == "emergency" or req_db.priority_score > 70):
            alert = alert_service.create_destination_cutoff_alert(
                db=db,
                request_id=req.request_id,
                handoff_village_id=rationale.get("handoff_village_id"),
                handoff_village_name=rationale.get("handoff_village_name")
            )
            audit_service.log_event(
                db=db,
                event_type="AlertCreated",
                payload={"alert_id": str(alert.id), "alert_type": alert.type},
                actor_id=None,
                correlation_id=req.request_id
            )

    return rationale

@app.post("/api/v1/deliveries", response_model=schemas.DeliveryResponse)
def dispatch_delivery(req: schemas.DeliveryCreate, db: Session = Depends(get_db), current_user: models.User = Depends(allow_control_room)):
    db_req = db.query(models.SupplyRequest).filter(models.SupplyRequest.id == req.supply_request_id).first()
    if not db_req:
        raise HTTPException(status_code=404, detail="Supply request not found")
        
    if not req.route_plan or not req.route_plan.get("feasible"):
        raise HTTPException(status_code=400, detail="Cannot dispatch without a feasible route plan.")
        
    db_delivery = models.Delivery(
        supply_request_id=req.supply_request_id,
        driver_id=req.driver_id,
        route_plan=req.route_plan,
        dispatched_quantity=req.dispatched_quantity if req.dispatched_quantity is not None else db_req.quantity,
        status="dispatched"
    )
    db.add(db_delivery)
    db_req.status = 'assigned'
    db.flush()
    
    db.add(models.EventLog(event_type="DispatchApproved", actor_id=current_user.id, correlation_id=db_delivery.id, payload=jsonable_encoder(req.route_plan)))
    db.commit()
    db.refresh(db_delivery)
    return db_delivery

@app.get("/api/v1/roads", response_model=List[schemas.RoadSegmentResponse])
def get_roads(db: Session = Depends(get_db)):
    return db.query(models.RoadSegment).all()

@app.get("/api/v1/villages", response_model=List[schemas.VillageResponse])
def get_villages(db: Session = Depends(get_db)):
    villages = db.query(models.Village, func.ST_Y(models.Village.geom).label('lat'), func.ST_X(models.Village.geom).label('lng')).all()
    result = []
    for v, lat, lng in villages:
        v_dict = v.__dict__.copy()
        v_dict['coords'] = [lat, lng]
        result.append(v_dict)
    return result

@app.get("/api/v1/roads/geojson")
def get_roads_geojson(db: Session = Depends(get_db)):
    roads = db.query(models.RoadSegment, func.ST_AsGeoJSON(models.RoadSegment.geom).label('geojson')).all()
    features = []
    for road, geojson_str in roads:
        features.append({
            "type": "Feature",
            "properties": {
                "id": str(road.id),
                "name": road.name,
                "accessibility_state": road.accessibility_state,
                "risk_level": road.risk_level,
                "is_bridge": road.is_bridge,
                "max_vehicle_weight_kg": road.max_vehicle_weight_kg,
                "disruption_probability": road.disruption_probability,
                "predicted_risk_band": road.predicted_risk_band,
                "risk_factors": road.risk_factors,
                "last_updated": road.last_updated.isoformat() if road.last_updated else None
            },
            "geometry": json.loads(geojson_str)
        })
    return {"type": "FeatureCollection", "features": features}

@app.post("/api/v1/environmental/sync")
def sync_environmental(db: Session = Depends(get_db), current_user: models.User = Depends(allow_control_room)):
    environmental_service.sync_environmental_data(db)
    prediction_service.update_disruption_predictions(db)
    return {"status": "success", "message": "Environmental data synced and disruption risk updated"}

@app.get("/api/v1/deliveries")
def get_deliveries(db: Session = Depends(get_db)):
    # Drivers see all active deliveries for simplicity in MVP
    return db.query(models.Delivery).order_by(models.Delivery.created_at.desc()).all()

@app.put("/api/v1/deliveries/{delivery_id}/pod", response_model=schemas.DeliveryResponse)
def submit_proof_of_delivery(
    delivery_id: UUID,
    received_quantity: int = Form(...),
    condition_status: str = Form(...),
    discrepancy_reason: Optional[str] = Form(None),
    receiver_name: Optional[str] = Form(None),
    receiver_contact: Optional[str] = Form(None),
    pod_notes: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(allow_driver)
):
    evidence_url = None
    if photo:
        if photo.content_type not in ["image/jpeg", "image/png"]:
            raise HTTPException(status_code=400, detail="Invalid photo format. Only JPEG/PNG allowed.")
        ext = photo.filename.split(".")[-1]
        filename = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(photo.file.read())
        evidence_url = f"/uploads/{filename}"

    pod_data = schemas.ProofOfDelivery(
        received_quantity=received_quantity,
        condition_status=condition_status,
        discrepancy_reason=discrepancy_reason,
        receiver_name=receiver_name,
        receiver_contact=receiver_contact,
        pod_notes=pod_notes
    )

    db_delivery = delivery_service.reconcile_delivery(db, delivery_id, pod_data, current_user.id, evidence_url)
    db.commit()
    db.refresh(db_delivery)
    return db_delivery


# ─────────────────────────────────────────────────────────────────────────────
# EPIC-07  Idempotent Offline Sync Endpoint
# ─────────────────────────────────────────────────────────────────────────────

VALID_SYNC_ACTION_TYPES = {'incident.create', 'telemetry.create', 'delivery.pod'}
MAX_SYNC_BATCH = 50  # hard cap; configurable

@app.post("/api/v1/sync", response_model=schemas.SyncBatchResponse)
def sync_offline_actions(
    req: schemas.SyncBatchRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Idempotent batch sync for offline-captured actions.
    Each action is processed exactly once — duplicate client_action_ids return
    the original result without re-executing the domain operation.
    """
    if len(req.actions) > MAX_SYNC_BATCH:
        raise HTTPException(status_code=400, detail=f"Batch too large. Max {MAX_SYNC_BATCH} actions per request.")

    results: list[schemas.SyncActionResult] = []

    for action in req.actions:
        caid = action.client_action_id

        # ── 1. IDEMPOTENCY CHECK ──────────────────────────────────────────────
        existing = db.query(models.ProcessedSyncAction).filter(
            models.ProcessedSyncAction.client_action_id == caid
        ).first()
        if existing:
            results.append(schemas.SyncActionResult(
                client_action_id=caid,
                status="duplicate",
                server_entity_id=existing.server_entity_id,
                detail="Already processed — original result returned."
            ))
            continue

        # ── 2. ACTION TYPE VALIDATION ─────────────────────────────────────────
        if action.action_type not in VALID_SYNC_ACTION_TYPES:
            _record_sync(db, caid, current_user.id, action.action_type, 'validation_failed', action.occurred_at, None)
            results.append(schemas.SyncActionResult(
                client_action_id=caid, status="validation_failed",
                detail=f"Unknown action_type: {action.action_type}"
            ))
            continue

        # ── 3. DISPATCH BY ACTION TYPE ────────────────────────────────────────
        try:
            if action.action_type == 'incident.create':
                result = _sync_incident_create(db, current_user, action)
            elif action.action_type == 'telemetry.create':
                result = _sync_telemetry_create(db, current_user, action)
            elif action.action_type == 'delivery.pod':
                result = _sync_delivery_pod(db, current_user, action)
            else:
                result = schemas.SyncActionResult(client_action_id=caid, status='rejected', detail='Unhandled type')

            # ── 4. ATOMIC IDEMPOTENCY RECORD ─────────────────────────────────
            _record_sync(db, caid, current_user.id, action.action_type, result.status, action.occurred_at, result.server_entity_id)
            db.commit()
            results.append(result)

        except HTTPException as e:
            db.rollback()
            _record_sync(db, caid, current_user.id, action.action_type, 'rejected', action.occurred_at, None)
            db.commit()
            results.append(schemas.SyncActionResult(
                client_action_id=caid, status='rejected', detail=e.detail
            ))
        except Exception as e:
            db.rollback()
            results.append(schemas.SyncActionResult(
                client_action_id=caid, status='rejected', detail='Internal processing error'
            ))

    db.add(models.EventLog(
        event_type="OfflineSyncBatchReceived",
        actor_id=current_user.id,
        correlation_id=None,
        payload={"sync_batch_id": str(req.sync_batch_id), "action_count": len(req.actions), "client_id": str(req.client_id)}
    ))
    db.commit()

    return schemas.SyncBatchResponse(
        sync_batch_id=req.sync_batch_id,
        processed_count=len(results),
        results=results
    )


def _record_sync(db, client_action_id, user_id, action_type, status, occurred_at, server_entity_id):
    """Write an idempotency record. Must be called before commit."""
    record = models.ProcessedSyncAction(
        client_action_id=client_action_id,
        user_id=user_id,
        action_type=action_type,
        result_status=status,
        server_entity_id=server_entity_id,
        occurred_at=occurred_at
    )
    db.add(record)


def _sync_incident_create(db, current_user, action: schemas.SyncActionItem) -> schemas.SyncActionResult:
    """Process an offline incident.create action using the same domain logic as the online path."""
    p = action.payload

    # Field-level validation
    required = ['road_segment_id', 'incident_type', 'severity', 'latitude', 'longitude']
    missing = [f for f in required if f not in p]
    if missing:
        return schemas.SyncActionResult(
            client_action_id=action.client_action_id,
            status='validation_failed',
            detail=f"Missing fields: {missing}"
        )

    lat, lng = float(p['latitude']), float(p['longitude'])
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return schemas.SyncActionResult(
            client_action_id=action.client_action_id,
            status='validation_failed', detail='Invalid coordinates'
        )

    # Authorization: field_officer or driver only
    if current_user.role not in ('field_officer', 'driver', 'control_room'):
        return schemas.SyncActionResult(
            client_action_id=action.client_action_id,
            status='authorization_failed', detail='Not authorized to report incidents'
        )

    road_segment_id = p['road_segment_id']
    incident_type = p['incident_type']
    severity = p['severity']

    confidence_score = 0.9 if current_user.role == 'field_officer' else 0.7
    geom = f"SRID=4326;POINT({lng} {lat})"

    db_incident = models.Incident(
        road_segment_id=road_segment_id,
        reporter_id=current_user.id,
        incident_type=incident_type,
        severity=severity,
        description=p.get('description'),
        evidence_url=None,  # photos require connectivity
        confidence_score=confidence_score,
        geom=geom
    )
    db.add(db_incident)
    db.flush()

    db.add(models.EventLog(
        event_type="IncidentReported",
        actor_id=current_user.id,
        correlation_id=db_incident.id,
        payload={"incident_type": incident_type, "severity": severity, "source": "offline_sync"}
    ))

    # Reuse EPIC-05 conflict/dispute logic
    db_road = db.query(models.RoadSegment).filter(models.RoadSegment.id == road_segment_id).first()
    if db_road:
        active_incidents = db.query(models.Incident).filter(
            models.Incident.road_segment_id == road_segment_id,
            models.Incident.status == 'pending_review'
        ).all()

        def implied_state(inc_type, sev):
            if inc_type in ['reopened', 'open']: return 'open'
            if sev == 'critical': return 'blocked'
            return 'hazardous'

        states = set(implied_state(i.incident_type, i.severity) for i in active_incidents)
        new_state = implied_state(incident_type, severity)
        result_status = 'accepted'

        if len(states) > 1 or (len(states) == 1 and list(states)[0] != new_state):
            db_road.accessibility_state = 'disputed'
            result_status = 'conflict'
        else:
            if new_state == 'blocked':
                db_road.accessibility_state = 'blocked'
            elif new_state == 'open':
                db_road.accessibility_state = 'open'

        db_road.last_updated = datetime.utcnow()
    else:
        result_status = 'accepted'

    return schemas.SyncActionResult(
        client_action_id=action.client_action_id,
        status=result_status,
        server_entity_id=db_incident.id
    )


def _sync_telemetry_create(db, current_user, action: schemas.SyncActionItem) -> schemas.SyncActionResult:
    """Process an offline telemetry.create action using the same domain logic as the online path."""
    p = action.payload

    required = ['delivery_id', 'source_type', 'latitude', 'longitude']
    missing = [f for f in required if f not in p]
    if missing:
        return schemas.SyncActionResult(
            client_action_id=action.client_action_id,
            status='validation_failed',
            detail=f"Missing fields: {missing}"
        )

    lat, lng = float(p['latitude']), float(p['longitude'])
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return schemas.SyncActionResult(
            client_action_id=action.client_action_id,
            status='validation_failed', detail='Invalid coordinates'
        )

    delivery_id = p['delivery_id']
    delivery = db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
    if not delivery:
        return schemas.SyncActionResult(
            client_action_id=action.client_action_id,
            status='rejected', detail='Delivery not found'
        )

    # Authorization: must be control_room OR the assigned driver
    if current_user.role != 'control_room' and (
        current_user.role != 'driver' or delivery.driver_id != current_user.id
    ):
        return schemas.SyncActionResult(
            client_action_id=action.client_action_id,
            status='authorization_failed',
            detail='Not authorized to submit telemetry for this delivery'
        )

    source_type = p.get('source_type', 'mobile_gps')
    if source_type == 'manual_checkpoint' and not p.get('checkpoint_name'):
        return schemas.SyncActionResult(
            client_action_id=action.client_action_id,
            status='validation_failed', detail='Manual checkpoints require checkpoint_name'
        )

    captured = action.occurred_at or datetime.utcnow()
    geom = f"SRID=4326;POINT({lng} {lat})"

    telemetry = models.DeliveryTelemetry(
        delivery_id=delivery_id,
        source_type=source_type,
        latitude=lat,
        longitude=lng,
        speed_kmh=p.get('speed_kmh'),
        battery_level=p.get('battery_level'),
        checkpoint_name=p.get('checkpoint_name'),
        captured_at=captured,
        geom=geom
    )
    db.add(telemetry)
    db.flush()

    # Update delivery current position only if this is newer than what we have
    if not delivery.last_ping_at or captured >= delivery.last_ping_at:
        delivery.last_known_lat = lat
        delivery.last_known_lng = lng
        delivery.last_ping_at = captured

    db.add(models.EventLog(
        event_type="TelemetryReceived",
        actor_id=current_user.id,
        correlation_id=delivery.id,
        payload={"source_type": source_type, "latitude": lat, "longitude": lng, "source": "offline_sync"}
    ))

    return schemas.SyncActionResult(
        client_action_id=action.client_action_id,
        status='accepted',
        server_entity_id=telemetry.id
    )

def _sync_delivery_pod(db, current_user, action: schemas.SyncActionItem) -> schemas.SyncActionResult:
    """Process an offline delivery.pod action."""
    p = action.payload
    
    required = ['delivery_id', 'received_quantity', 'condition_status']
    missing = [f for f in required if f not in p]
    if missing:
        return schemas.SyncActionResult(
            client_action_id=action.client_action_id,
            status='validation_failed',
            detail=f"Missing fields: {missing}"
        )
        
    delivery_id_str = p['delivery_id']
    try:
        delivery_id = UUID(delivery_id_str)
    except ValueError:
        return schemas.SyncActionResult(
            client_action_id=action.client_action_id,
            status='validation_failed', detail='Invalid delivery_id'
        )

    pod_data = schemas.ProofOfDelivery(
        received_quantity=p['received_quantity'],
        condition_status=p['condition_status'],
        discrepancy_reason=p.get('discrepancy_reason'),
        receiver_name=p.get('receiver_name'),
        receiver_contact=p.get('receiver_contact'),
        pod_notes=p.get('pod_notes')
    )

    try:
        db_delivery = delivery_service.reconcile_delivery(
            db, 
            delivery_id, 
            pod_data, 
            current_user.id, 
            pod_evidence_url=None, # Photo is omitted during offline sync
            occurred_at=action.occurred_at
        )
        return schemas.SyncActionResult(
            client_action_id=action.client_action_id,
            status='accepted',
            server_entity_id=db_delivery.id
        )
    except HTTPException as e:
        # Re-raise so the caller wrapper catches it and marks as rejected
        raise e

# --- EPIC-09: Alerts & Escalation ---
@app.get("/api/v1/alerts", response_model=List[schemas.AlertResponse])
def get_alerts(db: Session = Depends(get_db), current_user: models.User = Depends(allow_control_room)):
    return db.query(models.Alert).filter(models.Alert.status == "active").all()

@app.post("/api/v1/alerts/{alert_id}/acknowledge", response_model=schemas.AlertResponse)
def ack_alert(alert_id: UUID, db: Session = Depends(get_db), current_user: models.User = Depends(allow_control_room)):
    from . import alert_service, audit_service
    alert = alert_service.acknowledge_alert(db, alert_id, current_user.id)
    if not alert: 
        raise HTTPException(status_code=404, detail="Alert not found")
    audit_service.log_event(db, "AlertAcknowledged", {"alert_id": str(alert_id)}, current_user.id, alert.related_request_id)
    return alert

@app.post("/api/v1/alerts/{alert_id}/escalate", response_model=schemas.AirEscalationResponse)
def escalate_alert(alert_id: UUID, req: schemas.AirEscalationCreate, db: Session = Depends(get_db), current_user: models.User = Depends(allow_control_room)):
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert or not alert.related_request_id:
        raise HTTPException(status_code=404, detail="Alert not found or invalid")
    from . import alert_service, audit_service
    escalation = alert_service.approve_escalation(db, alert.related_request_id, current_user.id, req.reason, req.decision)
    audit_service.log_event(db, "AirEscalationApproved" if req.decision == "approved" else "AirEscalationRejected", {"decision": req.decision, "reason": req.reason}, current_user.id, alert.related_request_id)
    return escalation

# --- EPIC-10: Audit Timeline & Export ---
@app.get("/api/v1/audit/timeline/{correlation_id}", response_model=List[schemas.EventLogResponse])
def get_audit_timeline(correlation_id: UUID, db: Session = Depends(get_db), current_user: models.User = Depends(allow_control_room)):
    from . import audit_service
    is_valid, events = audit_service.verify_chain(db, correlation_id)
    results = []
    for e in events:
        schema = schemas.EventLogResponse.model_validate(e)
        schema.integrity_verified = is_valid
        results.append(schema)
    return results

@app.get("/api/v1/audit/export")
def export_audit_csv(correlation_id: Optional[UUID] = None, db: Session = Depends(get_db), current_user: models.User = Depends(allow_control_room)):
    from fastapi.responses import PlainTextResponse
    import csv, io
    query = db.query(models.EventLog).order_by(models.EventLog.occurred_at.asc())
    if correlation_id:
        query = query.filter(models.EventLog.correlation_id == correlation_id)
    events = query.all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Time", "Event Type", "Actor ID", "Correlation ID", "Payload", "Integrity Status"])
    
    for e in events:
        writer.writerow([
            e.occurred_at.isoformat(),
            e.event_type,
            str(e.actor_id) if e.actor_id else "",
            str(e.correlation_id) if e.correlation_id else "",
            json.dumps(e.payload),
            "Verified" if e.checksum else "Unknown"
        ])
    return PlainTextResponse(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=audit_export.csv"})