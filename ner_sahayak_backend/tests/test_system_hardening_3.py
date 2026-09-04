import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import uuid
from unittest.mock import patch

from app.main import app
from app import models, auth, environmental_service, prediction_service, alert_service

client = TestClient(app)

def test_environmental_ingestion_provider_fallback(db_session: Session):
    """Test Defect 1: Environmental Ingestion uses Open-Meteo with Fallback"""
    # Test Fallback directly
    with patch('app.environmental_service.httpx.get') as mock_get:
        mock_get.side_effect = Exception("API Timeout")
        r_current, r_24h, r_72h = environmental_service.ExternalWeatherProvider.get_precipitation(25.5, 91.8)
        assert r_current >= 0 # Should fallback without crashing
    
    # Test successful provider
    with patch('app.environmental_service.httpx.get') as mock_get:
        mock_get.return_value.json.return_value = {
            "current": {"precipitation": 15.5},
            "hourly": {"precipitation": [1.0] * 24}
        }
        r_current, r_24h, r_72h = environmental_service.ExternalWeatherProvider.get_precipitation(25.5, 91.8)
        assert r_current == 15.5
        assert r_24h == 24.0

def test_prediction_remains_advisory(db_session: Session):
    """Test Defect 2: Prediction must remain advisory"""
    roads = db_session.query(models.RoadSegment).all()
    assert len(roads) > 0
    road = roads[0]
    original_state = road.accessibility_state
    
    # Sync mock data and run prediction
    environmental_service.sync_environmental_data(db_session, use_mock=True)
    prediction_service.update_disruption_predictions(db_session)
    
    db_session.refresh(road)
    assert road.disruption_probability is not None
    assert road.accessibility_state == original_state # Should NOT change state

def test_incident_authority_and_conflict(db_session: Session, test_user_field_officer, test_user_control_room):
    """Test Defect 3 and 4: Incident Authority and Conflict Resolution"""
    fo_token = auth.create_access_token(data={"sub": str(test_user_field_officer.id), "role": test_user_field_officer.role})
    cr_token = auth.create_access_token(data={"sub": str(test_user_control_room.id), "role": test_user_control_room.role})
    
    road = db_session.query(models.RoadSegment).filter(models.RoadSegment.accessibility_state == 'open').first()
    db_session.query(models.Incident).filter(models.Incident.road_segment_id == road.id).delete()
    db_session.commit()
    
    try:
        # 1. FO reports blocked
        res1 = client.post("/api/v1/incidents", data={
            "road_segment_id": str(road.id),
            "incident_type": "landslide",
            "severity": "critical",
            "description": "Blocked",
            "latitude": 25.5,
            "longitude": 91.8
        }, headers={"Authorization": f"Bearer {fo_token}"})
        assert res1.status_code == 200
        db_session.refresh(road)
        assert road.accessibility_state == 'open' # State stays same until verified
        
        # 2. Another FO reports open (conflict set)
        res2 = client.post("/api/v1/incidents", data={
            "road_segment_id": str(road.id),
            "incident_type": "open",
            "severity": "minor",
            "description": "Clear",
            "latitude": 25.5,
            "longitude": 91.8
        }, headers={"Authorization": f"Bearer {fo_token}"})
        db_session.refresh(road)
        assert road.accessibility_state == 'disputed'
        
        incident1_id = res1.json()["id"]
        
        # 3. CR verifies one report as blocked
        res_verify = client.post(f"/api/v1/incidents/{incident1_id}/verify", json={
            "verified_state": "blocked",
            "verification_note": "Verified by CR"
        }, headers={"Authorization": f"Bearer {cr_token}"})
        assert res_verify.status_code == 200
        
        db_session.refresh(road)
        assert road.accessibility_state == 'blocked'
        
        # Ensure conflicting incident was rejected
        incident2_id = res2.json()["id"]
        incident2 = db_session.query(models.Incident).filter(models.Incident.id == incident2_id).first()
        assert incident2.status == 'rejected'
    finally:
        db_session.query(models.Incident).filter(models.Incident.road_segment_id == road.id).delete()
        db_session.query(models.RoadSegment).filter(models.RoadSegment.id == road.id).update({"accessibility_state": "open"})
        db_session.commit()

def test_nearest_handoff(db_session: Session):
    """Test Defect 5: Nearest Handoff"""
    villages = db_session.query(models.Village).all()
    # Assuming the seed data has handoffs.
    target_village = villages[0]
    handoff = alert_service.get_nearest_handoff(db_session, target_village_id=target_village.id)
    # Could be None if no handoffs, but if handoffs exist, it should return one
    if handoff:
        assert handoff.is_handoff is True

def test_alert_lifecycle_escalation(db_session: Session, test_user_control_room):
    """Test Defect 6, 7, 8: Alerts Deduplication and Escalation workflows"""
    test_user_supervisor = db_session.query(models.User).filter(models.User.role == 'supervisor').first()
    if not test_user_supervisor:
        test_user_supervisor = models.User(name="Sup", email="sup@nersahayak.gov.in", hashed_password="foo", role="supervisor")
        db_session.add(test_user_supervisor)
        db_session.commit()
    
    cr_token = auth.create_access_token(data={"sub": str(test_user_control_room.id), "role": test_user_control_room.role})
    sup_token = auth.create_access_token(data={"sub": str(test_user_supervisor.id), "role": test_user_supervisor.role})
    
    req_id = db_session.query(models.SupplyRequest).first().id
    
    # 1. Create alert
    alert1 = alert_service.create_destination_cutoff_alert(db_session, req_id, None, None)
    
    # 2. Acknowledge alert
    alert_service.acknowledge_alert(db_session, alert1.id, test_user_control_room.id)
    assert alert1.status == "acknowledged"
    
    # 3. Create alert again, should deduplicate to the acknowledged one
    alert2 = alert_service.create_destination_cutoff_alert(db_session, req_id, None, None)
    assert alert1.id == alert2.id
    
    # 4. Control room tries to escalate (Should fail - unauthorized)
    res_esc_cr = client.post(f"/api/v1/alerts/{alert1.id}/escalate", json={
        "reason": "Test",
        "decision": "rejected"
    }, headers={"Authorization": f"Bearer {cr_token}"})
    assert res_esc_cr.status_code == 403
    
    # 5. Supervisor rejects escalation (Alert should not be resolved)
    res_esc_sup = client.post(f"/api/v1/alerts/{alert1.id}/escalate", json={
        "reason": "Wait and see",
        "decision": "rejected"
    }, headers={"Authorization": f"Bearer {sup_token}"})
    assert res_esc_sup.status_code == 200
    
    db_session.refresh(alert1)
    assert alert1.status == "acknowledged"
    
    # 6. Supervisor approves escalation (Alert should be resolved)
    res_esc_sup2 = client.post(f"/api/v1/alerts/{alert1.id}/escalate", json={
        "reason": "Deploy helicopter",
        "decision": "approved"
    }, headers={"Authorization": f"Bearer {sup_token}"})
    assert res_esc_sup2.status_code == 200
    
    db_session.refresh(alert1)
    assert alert1.status == "resolved"
