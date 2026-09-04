from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session
from .models import Alert, AirEscalation, Village

def create_destination_cutoff_alert(
    db: Session, 
    request_id: UUID, 
    handoff_village_id: Optional[UUID], 
    handoff_village_name: Optional[str]
) -> Alert:
    """
    Creates or updates a critical alert for a destination cut-off scenario.
    """
    # Deduplication: Check if there's an active or acknowledged alert for this request
    existing = db.query(Alert).filter(
        Alert.related_request_id == request_id,
        Alert.type == "destination_cut_off",
        Alert.status.in_(["active", "acknowledged"])
    ).first()

    payload = {
        "handoff_village_id": str(handoff_village_id) if handoff_village_id else None,
        "handoff_village_name": handoff_village_name
    }

    if existing:
        # Just update the payload if it changed, or leave it
        existing.recommendation_payload = payload
        db.commit()
        db.refresh(existing)
        return existing

    alert = Alert(
        type="destination_cut_off",
        severity="CRITICAL",
        title="Critical Destination Cut Off",
        message="No feasible safe road routes available for critical supply request.",
        related_request_id=request_id,
        status="active",
        recommendation_payload=payload
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert

def get_nearest_handoff(db: Session, target_village_id: UUID = None) -> Optional[Village]:
    """
    Finds the nearest configured handoff point (hub/helipad) to the target village.
    Uses PostGIS ST_Distance.
    """
    if target_village_id:
        target = db.query(Village).filter(Village.id == target_village_id).first()
        if target:
            from sqlalchemy import func
            return db.query(Village).filter(Village.is_handoff == True).order_by(
                func.ST_Distance(Village.geom, target.geom)
            ).first()
    
    return db.query(Village).filter(Village.is_handoff == True).first()

def acknowledge_alert(db: Session, alert_id: UUID, actor_id: UUID) -> Optional[Alert]:
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        return None
    
    alert.status = "acknowledged"
    alert.acknowledged_by = actor_id
    from datetime import datetime
    alert.acknowledged_at = datetime.utcnow()
    
    db.commit()
    db.refresh(alert)
    return alert

def approve_escalation(db: Session, request_id: UUID, actor_id: UUID, reason: str, decision: str) -> AirEscalation:
    escalation = AirEscalation(
        request_id=request_id,
        approved_by=actor_id,
        reason=reason,
        decision=decision
    )
    db.add(escalation)
    
    # Resolve related active alerts only if approved
    if decision == "approved":
        alerts = db.query(Alert).filter(
            Alert.related_request_id == request_id,
            Alert.status != "resolved"
        ).all()
        for alert in alerts:
            alert.status = "resolved"
        
    db.commit()
    db.refresh(escalation)
    return escalation
