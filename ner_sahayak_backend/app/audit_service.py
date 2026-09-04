import hashlib
import json
from uuid import UUID
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from .models import EventLog

def _serialize_for_hash(payload: Any) -> str:
    """
    Produce a deterministic JSON string for hashing.
    Sorts keys and removes whitespace to ensure stable serialization.
    """
    def convert_uuids_and_dates(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: convert_uuids_and_dates(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_uuids_and_dates(item) for item in obj]
        elif isinstance(obj, UUID):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj

    cleaned = convert_uuids_and_dates(payload)
    return json.dumps(cleaned, sort_keys=True, separators=(',', ':'))

def _compute_hash(event_type: str, actor_id: Optional[UUID], correlation_id: Optional[UUID], payload: Dict[str, Any], previous_hash: Optional[str]) -> str:
    """
    Compute SHA-256 hash for the event.
    """
    data = {
        "event_type": event_type,
        "actor_id": str(actor_id) if actor_id else None,
        "correlation_id": str(correlation_id) if correlation_id else None,
        "payload": payload,
        "previous_hash": previous_hash
    }
    serialized = _serialize_for_hash(data)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()

def log_event(db: Session, event_type: str, payload: Dict[str, Any], actor_id: Optional[UUID] = None, correlation_id: Optional[UUID] = None) -> EventLog:
    """
    Log an event and compute its checksum based on the previous event in the chain.
    """
    # Find the previous event by occurred_at for this correlation_id, or globally if no correlation_id
    if correlation_id:
        prev_event = db.query(EventLog).filter(EventLog.correlation_id == correlation_id).order_by(EventLog.occurred_at.desc(), EventLog.event_id.desc()).first()
    else:
        prev_event = None # No correlation chain; could chain globally, but correlation is preferred

    prev_hash = prev_event.checksum if prev_event else "GENESIS"
    
    current_hash = _compute_hash(event_type, actor_id, correlation_id, payload, prev_hash)

    event = EventLog(
        event_type=event_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        payload=payload,
        previous_hash=prev_hash,
        checksum=current_hash,
        occurred_at=datetime.utcnow(),
        received_at=datetime.utcnow()
    )
    
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

def verify_chain(db: Session, correlation_id: UUID) -> Tuple[bool, list[EventLog]]:
    """
    Verify the integrity of a chain for a given correlation_id.
    Returns (is_valid, list_of_events)
    """
    events = db.query(EventLog).filter(EventLog.correlation_id == correlation_id).order_by(EventLog.occurred_at.asc(), EventLog.event_id.asc()).all()
    
    if not events:
        return True, []
    
    expected_prev_hash = "GENESIS"
    is_valid = True
    
    for event in events:
        # Check if the stored previous_hash matches our expectation
        if event.previous_hash != expected_prev_hash:
            is_valid = False
            # We don't break immediately so we can still return the events for inspection
        
        # Recompute current hash
        computed_hash = _compute_hash(event.event_type, event.actor_id, event.correlation_id, event.payload, expected_prev_hash)
        
        if computed_hash != event.checksum:
            is_valid = False
            
        expected_prev_hash = event.checksum
        
    return is_valid, events
