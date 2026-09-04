import pytest
from uuid import uuid4
from conftest import get, post

def test_epic9_alerts(control_room_token: str, db_session):
    # 1. Create a critical supply request (via DB directly)
    from app import models
    request = db_session.query(models.SupplyRequest).first()
    alert = models.Alert(
        type="destination_cut_off",
        severity="CRITICAL",
        title="Test Alert",
        message="Test Message",
        related_request_id=request.id,
        status="active"
    )
    db_session.add(alert)
    db_session.commit()
    
    # 2. Get Alerts
    resp = get("/api/v1/alerts", token=control_room_token)
    assert resp.status_code == 200
    alerts = resp.json()
    assert len(alerts) > 0
    
    # 3. Acknowledge Alert
    alert_id = alerts[0]["id"]
    ack_resp = post(f"/api/v1/alerts/{alert_id}/acknowledge", token=control_room_token)
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "acknowledged"
    
    # 3.5 Attempt unauthorized escalation
    esc_req = {"reason": "Test Escalation", "decision": "approved"}
    esc_resp_unauth = post(f"/api/v1/alerts/{alert_id}/escalate", json=esc_req, token=control_room_token)
    assert esc_resp_unauth.status_code == 403
    
    # 4. Escalate Alert with supervisor token
    from app import auth
    test_user_supervisor = db_session.query(models.User).filter(models.User.role == 'supervisor').first()
    if not test_user_supervisor:
        test_user_supervisor = models.User(name="Sup", email="sup@nersahayak.gov.in", hashed_password="foo", role="supervisor")
        db_session.add(test_user_supervisor)
        db_session.commit()
    sup_token = auth.create_access_token(data={"sub": str(test_user_supervisor.id), "role": test_user_supervisor.role})
    
    esc_resp = post(f"/api/v1/alerts/{alert_id}/escalate", json=esc_req, token=sup_token)
    assert esc_resp.status_code == 200
    assert esc_resp.json()["decision"] == "approved"
    
def test_epic10_audit(control_room_token: str, db_session):
    # 1. Create audit logs
    from app import audit_service
    correlation_id = uuid4()
    
    evt1 = audit_service.log_event(db_session, "TestEvent1", {"test": 1}, correlation_id=correlation_id)
    evt2 = audit_service.log_event(db_session, "TestEvent2", {"test": 2}, correlation_id=correlation_id)
    
    assert evt2.previous_hash == evt1.checksum
    
    # 2. Fetch timeline
    resp = get(f"/api/v1/audit/timeline/{correlation_id}", token=control_room_token)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["integrity_verified"] == True
    assert data[1]["integrity_verified"] == True
    
    # 3. Tamper with DB
    evt1.payload = {"test": "tampered"}
    db_session.commit()
    
    # 4. Fetch timeline again
    resp2 = get(f"/api/v1/audit/timeline/{correlation_id}", token=control_room_token)
    assert resp2.status_code == 200
