from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import json
from sqlalchemy import func

from . import models, schemas, auth, graph_engine, priority_engine, routing_service
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

@app.get("/api/v1/users", response_model=List[schemas.UserResponse])
def get_users(role: Optional[str] = None, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    query = db.query(models.User)
    if role:
        query = query.filter(models.User.role == role)
    return query.all()

@app.post("/api/v1/requests", response_model=schemas.SupplyRequestResponse)
def create_supply_request(req: schemas.SupplyRequestCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    db_request = models.SupplyRequest(**req.model_dump())
    
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

    db.add(models.EventLog(event_type="SupplyRequestCreated", actor_id=current_user.id, correlation_id=db_request.id, payload=req.model_dump()))
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

@app.post("/api/v1/routes/evaluate", response_model=schemas.RouteEvaluationResponse)
def evaluate_route(req: schemas.RouteEvaluationRequest, db: Session = Depends(get_db), current_user: models.User = Depends(allow_control_room)):
    return routing_service.evaluate_routes(
        db=db,
        source_id=str(req.source_village_id),
        target_id=str(req.target_village_id),
        vehicle_constraints=req.vehicle_constraints,
        policy_weights=req.policy_weights
    )

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
        status="dispatched"
    )
    db.add(db_delivery)
    db_req.status = 'assigned'
    db.flush()
    
    db.add(models.EventLog(event_type="DispatchApproved", actor_id=current_user.id, correlation_id=db_delivery.id, payload=req.route_plan))
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
                "last_updated": road.last_updated.isoformat() if road.last_updated else None
            },
            "geometry": json.loads(geojson_str)
        })
    return {"type": "FeatureCollection", "features": features}

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
