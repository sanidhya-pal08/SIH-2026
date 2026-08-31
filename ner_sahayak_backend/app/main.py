from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime

from . import models, schemas, auth, graph_engine
from .database import engine, get_db, SessionLocal
from .seed import seed_demo_graph

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="NER Sahayak API",
    description="Core backend for NER Sahayak logistics platform with RBAC and GIS Routing",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to the frontend URL
    allow_credentials=True,
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

@app.post("/api/v1/requests", response_model=schemas.SupplyRequestResponse)
def create_supply_request(req: schemas.SupplyRequestCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    db_request = models.SupplyRequest(**req.model_dump())
    db_request.priority_score = 75.5 if req.urgency == 'emergency' else 10.0
    db.add(db_request)
    db.flush()

    db.add(models.EventLog(event_type="SupplyRequestCreated", actor_id=current_user.id, correlation_id=db_request.id, payload=req.model_dump()))
    db.commit()
    db.refresh(db_request)
    return db_request

@app.get("/api/v1/requests", response_model=List[schemas.SupplyRequestResponse])
def list_supply_requests(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: models.User = Depends(allow_control_room)):
    return db.query(models.SupplyRequest).order_by(models.SupplyRequest.priority_score.desc()).offset(skip).limit(limit).all()

@app.post("/api/v1/incidents", response_model=schemas.IncidentResponse)
def report_incident(req: schemas.IncidentCreate, db: Session = Depends(get_db), current_user: models.User = Depends(allow_field_staff)):
    db_incident = models.Incident(**req.model_dump())
    db.add(db_incident)
    db.flush()
    
    db_road = db.query(models.RoadSegment).filter(models.RoadSegment.id == req.road_segment_id).first()
    if db_road:
        db_road.accessibility_state = 'blocked' if req.incident_type in ['landslide', 'bridge_failure'] else 'hazardous'
        db_road.last_updated = datetime.utcnow()

    db.add(models.EventLog(event_type="RoadAccessibilityChanged", actor_id=current_user.id, correlation_id=db_incident.id, payload={"incident_type": req.incident_type, "new_state": db_road.accessibility_state if db_road else "unknown"}))
    db.commit()
    db.refresh(db_incident)
    return db_incident

@app.post("/api/v1/deliveries", response_model=schemas.DeliveryResponse)
def dispatch_delivery(req: schemas.DeliveryCreate, db: Session = Depends(get_db), current_user: models.User = Depends(allow_control_room)):
    # 1. Fetch source (HQ or current village) and target (Request destination)
    db_req = db.query(models.SupplyRequest).filter(models.SupplyRequest.id == req.supply_request_id).first()
    if not db_req:
        raise HTTPException(status_code=404, detail="Supply request not found")
        
    # Assume source is some HQ node for now, or driver location. We'll use a hardcoded node ID from the DB in reality.
    target_node = str(db_req.village_id)
    
    # 2. Graph Routing Math!
    nodes = db.query(models.Village).all()
    edges = db.query(models.RoadSegment).all()
    
    if not nodes or not edges:
        raise HTTPException(status_code=503, detail="Graph not seeded in PostGIS yet.")
        
    source_node = str(nodes[0].id) # Simple mock: start at the first village (Base Camp)

    graph = graph_engine.build_graph(nodes, edges)
    pruned_graph, pruned_log = graph_engine.prune_graph(
        graph, 
        vehicle_weight_kg=req.vehicle_constraints.weight_kg if req.vehicle_constraints else None,
        vehicle_height_m=req.vehicle_constraints.height_m if req.vehicle_constraints else None,
        is_hazmat=req.vehicle_constraints.is_hazmat if req.vehicle_constraints else False
    )
    
    weighted_graph = graph_engine.apply_policy_weights(
        pruned_graph,
        w_delay=req.policy_weights.delay if req.policy_weights else 1.0,
        w_risk=req.policy_weights.risk if req.policy_weights else 1.0,
        w_failure=req.policy_weights.failure if req.policy_weights else 1.0,
        w_resource=req.policy_weights.resource if req.policy_weights else 1.0
    )
    
    paths = graph_engine.find_k_shortest_paths(weighted_graph, source_node, target_node, k=3)
    confidence = graph_engine.compute_confidence(paths)
    rationale = graph_engine.build_rationale(paths, pruned_log, confidence)
    
    if not paths:
        raise HTTPException(status_code=400, detail="No feasible route found. Escalate to air delivery.")

    # 3. Create delivery using the mathematically proven best route
    db_delivery = models.Delivery(
        supply_request_id=req.supply_request_id,
        driver_id=req.driver_id,
        route_plan=rationale,
        status="dispatched"
    )
    db.add(db_delivery)
    db_req.status = 'assigned'
    db.flush()
    
    db.add(models.EventLog(event_type="DispatchApproved", actor_id=current_user.id, correlation_id=db_delivery.id, payload=rationale))
    db.commit()
    db.refresh(db_delivery)
    return db_delivery

@app.get("/api/v1/roads")
def get_roads(db: Session = Depends(get_db)):
    return db.query(models.RoadSegment).all()

@app.get("/api/v1/villages")
def get_villages(db: Session = Depends(get_db)):
    return db.query(models.Village).all()

@app.get("/api/v1/deliveries")
def get_deliveries(db: Session = Depends(get_db)):
    # Drivers see all active deliveries for simplicity in MVP
    return db.query(models.Delivery).order_by(models.Delivery.created_at.desc()).all()

@app.put("/api/v1/deliveries/{delivery_id}/pod", response_model=schemas.DeliveryResponse)
def submit_proof_of_delivery(delivery_id: UUID, req: schemas.ProofOfDelivery, db: Session = Depends(get_db), current_user: models.User = Depends(allow_driver)):
    db_delivery = db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
    if not db_delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
        
    db_delivery.status = 'delivered'
    db_delivery.pod_notes = req.pod_notes
    db_delivery.delivered_at = datetime.utcnow()
    
    db_req = db.query(models.SupplyRequest).filter(models.SupplyRequest.id == db_delivery.supply_request_id).first()
    if db_req:
        db_req.status = 'delivered'

    db.add(models.EventLog(event_type="DeliveryClosed", actor_id=current_user.id, correlation_id=delivery_id, payload={"pod_notes": req.pod_notes, "status": "delivered"}))
    db.commit()
    db.refresh(db_delivery)
    return db_delivery
