from sqlalchemy.orm import Session
from uuid import UUID
from fastapi import HTTPException
from datetime import datetime

from . import models, schemas
from .schemas import ProofOfDelivery

def reconcile_delivery(
    db: Session,
    delivery_id: UUID,
    pod_data: ProofOfDelivery,
    user_id: UUID,
    pod_evidence_url: str = None,
    occurred_at: datetime = None
) -> models.Delivery:
    """
    Authoritative service to reconcile a proof of delivery.
    Ensures safe quantity calculations and creates follow-up requests if needed.
    """
    delivery = db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
        
    if delivery.status in ['delivered', 'completed_with_discrepancy']:
        # Idempotency safety — if already closed, just return it. 
        # (Though offline sync handles idempotency externally, online retries could hit this).
        return delivery

    # Quantity Validation
    if pod_data.received_quantity < 0 or pod_data.received_quantity > delivery.dispatched_quantity:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid received_quantity: must be between 0 and {delivery.dispatched_quantity}"
        )

    if pod_data.received_quantity < delivery.dispatched_quantity and not pod_data.discrepancy_reason:
        raise HTTPException(status_code=400, detail="Discrepancy reason is required for partial deliveries.")
        
    # Update Delivery Status
    if pod_data.received_quantity < delivery.dispatched_quantity:
        delivery.status = 'completed_with_discrepancy'
    else:
        delivery.status = 'delivered'

    delivery.received_quantity = pod_data.received_quantity
    delivery.condition_status = pod_data.condition_status
    delivery.discrepancy_reason = pod_data.discrepancy_reason
    delivery.receiver_name = pod_data.receiver_name
    delivery.receiver_contact = pod_data.receiver_contact
    delivery.pod_evidence_url = pod_evidence_url
    delivery.pod_notes = pod_data.pod_notes
    delivery.delivered_at = occurred_at or datetime.utcnow()

    # Reconcile Supply Request
    request = db.query(models.SupplyRequest).filter(models.SupplyRequest.id == delivery.supply_request_id).first()
    
    if request:
        request.fulfilled_quantity += pod_data.received_quantity
        
        if request.fulfilled_quantity >= request.quantity:
            request.status = 'fulfilled'
        else:
            request.status = 'partially_fulfilled'
            
            # Generate Follow-up Request for remaining amount
            remaining = request.quantity - request.fulfilled_quantity
            
            # Check if a child request already exists for this parent
            existing_child = db.query(models.SupplyRequest).filter(
                models.SupplyRequest.parent_request_id == request.id,
                models.SupplyRequest.status.in_(['open', 'assigned', 'pending', 'partially_fulfilled'])
            ).first()
            
            if existing_child:
                # Update existing unmet requirement instead of spamming duplicates
                existing_child.quantity += remaining
            else:
                child_request = models.SupplyRequest(
                    village_id=request.village_id,
                    requester_id=request.requester_id,
                    commodity_category=request.commodity_category,
                    commodity=request.commodity,
                    quantity=remaining,
                    urgency=request.urgency,
                    priority_score=request.priority_score,
                    is_overridden=request.is_overridden,
                    override_reason="Auto-generated due to partial delivery",
                    status='open',
                    parent_request_id=request.id
                )
                db.add(child_request)

    # Emit Audit Event
    db.add(models.EventLog(
        event_type="DeliveryReconciled",
        actor_id=user_id,
        correlation_id=delivery.id,
        payload={
            "supply_request_id": str(request.id) if request else None,
            "dispatched_quantity": delivery.dispatched_quantity,
            "received_quantity": delivery.received_quantity,
            "condition_status": delivery.condition_status,
            "status": delivery.status
        }
    ))

    db.flush()
    return delivery
