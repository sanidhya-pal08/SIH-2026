from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime, timedelta

from . import models, schemas, auth
from .database import engine, get_db

# Create all tables (In production, use Alembic migrations instead)
# models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="NER Sahayak API",
    description="Core backend for NER Sahayak logistics platform with RBAC",
    version="1.0.0"
)

# Initialize Role Checkers
allow_control_room = auth.RoleChecker(["control_room"])
allow_field_staff = auth.RoleChecker(["field_officer", "driver"])
allow_driver = auth.RoleChecker(["driver"])

@app.get("/")
def read_root():
    return {"message": "NER Sahayak API is running securely"}

# ==========================================
# 0. AUTHENTICATION & USERS
# ==========================================

@app.post("/api/v1/auth/register", response_model=schemas.UserResponse)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.phone_number == user.phone_number).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Phone number already registered")
        
    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(
        name=user.name, 
        phone_number=user.phone_number,
        role=user.role, 
        district=user.district,
        hashed_password=hashed_password
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/api/v1/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone_number == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone number or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth.create_access_token(data={"sub": str(user.id), "role": user.role})
    return {"access_token": access_token, "token_type": "bearer", "role": user.role, "user_id": user.id}


# ==========================================
# 1. SUPPLY REQUESTS (Control Room & Field)
# ==========================================

@app.post("/api/v1/requests", response_model=schemas.SupplyRequestResponse)
def create_supply_request(
    req: schemas.SupplyRequestCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    db_request = models.SupplyRequest(**req.model_dump())
    db_request.priority_score = 75.5 if req.urgency == 'emergency' else 10.0
    
    db.add(db_request)
    db.flush()

    event = models.EventLog(
        event_type="SupplyRequestCreated",
        actor_id=current_user.id,
        correlation_id=db_request.id,
        payload=req.model_dump()
    )
    db.add(event)
    db.commit()
    db.refresh(db_request)
    return db_request

@app.get("/api/v1/requests", response_model=List[schemas.SupplyRequestResponse])
def list_supply_requests(
    skip: int = 0, limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(allow_control_room) # Only Control Room sees the global queue
):
    return db.query(models.SupplyRequest).order_by(models.SupplyRequest.priority_score.desc()).offset(skip).limit(limit).all()


# ==========================================
# 2. INCIDENTS (Field Reports / Disruptions)
# ==========================================

@app.post("/api/v1/incidents", response_model=schemas.IncidentResponse)
def report_incident(
    req: schemas.IncidentCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(allow_field_staff) # Only Field Staff & Drivers report blockages
):
    db_incident = models.Incident(**req.model_dump())
    db.add(db_incident)
    db.flush()
    
    db_road = db.query(models.RoadSegment).filter(models.RoadSegment.id == req.road_segment_id).first()
    if db_road:
        db_road.accessibility_state = 'blocked' if req.incident_type in ['landslide', 'bridge_failure'] else 'hazardous'
        db_road.last_updated = datetime.utcnow()

    event = models.EventLog(
        event_type="RoadAccessibilityChanged",
        actor_id=current_user.id,
        correlation_id=db_incident.id,
        payload={"incident_type": req.incident_type, "new_state": db_road.accessibility_state if db_road else "unknown"}
    )
    db.add(event)
    db.commit()
    db.refresh(db_incident)
    return db_incident

@app.get("/api/v1/incidents", response_model=List[schemas.IncidentResponse])
def list_active_incidents(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    return db.query(models.Incident).filter(models.Incident.status != 'resolved').all()


# ==========================================
# 3. DELIVERIES & DISPATCH
# ==========================================

@app.post("/api/v1/deliveries", response_model=schemas.DeliveryResponse)
def dispatch_delivery(
    req: schemas.DeliveryCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(allow_control_room) # STRICTLY Control Room approves routes
):
    db_delivery = models.Delivery(**req.model_dump())
    db.add(db_delivery)
    db.flush()
    
    db_req = db.query(models.SupplyRequest).filter(models.SupplyRequest.id == req.supply_request_id).first()
    if db_req:
        db_req.status = 'assigned'
    
    event = models.EventLog(
        event_type="DispatchApproved",
        actor_id=current_user.id,
        correlation_id=db_delivery.id,
        payload=req.model_dump()
    )
    db.add(event)
    db.commit()
    db.refresh(db_delivery)
    return db_delivery

@app.put("/api/v1/deliveries/{delivery_id}/pod", response_model=schemas.DeliveryResponse)
def submit_proof_of_delivery(
    delivery_id: UUID, 
    req: schemas.ProofOfDelivery, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(allow_driver) # STRICTLY Drivers submit PoD
):
    db_delivery = db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
    if not db_delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
        
    db_delivery.status = 'delivered'
    db_delivery.pod_notes = req.pod_notes
    db_delivery.delivered_at = datetime.utcnow()
    
    db_req = db.query(models.SupplyRequest).filter(models.SupplyRequest.id == db_delivery.supply_request_id).first()
    if db_req:
        db_req.status = 'delivered'

    event = models.EventLog(
        event_type="DeliveryClosed",
        actor_id=current_user.id,
        correlation_id=delivery_id,
        payload={"pod_notes": req.pod_notes, "status": "delivered"}
    )
    db.add(event)
    db.commit()
    db.refresh(db_delivery)
    return db_delivery
