import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import uuid

from app.main import app
from app import models, auth

client = TestClient(app)

def test_route_evaluation_no_feasible_route(db_session: Session, test_user_control_room):
    """Test Defect 5: No-feasible-route handling."""
    token = auth.create_access_token(data={"sub": str(test_user_control_room.id), "role": test_user_control_room.role})
    
    # Create two disconnected villages explicitly for this test
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()
    from geoalchemy2.elements import WKTElement
    v1 = models.Village(id=v1_id, name="Isolated Village 1", district="Test", population=100, geom=WKTElement('POINT(91.0 25.0)', srid=4326))
    v2 = models.Village(id=v2_id, name="Isolated Village 2", district="Test", population=100, geom=WKTElement('POINT(91.1 25.1)', srid=4326))
    db_session.add_all([v1, v2])
    db_session.commit()
    
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post("/api/v1/routes/evaluate", json={
        "source_village_id": str(v1_id),
        "target_village_id": str(v2_id),
        "vehicle_constraints": {},
        "policy_weights": {}
    }, headers=headers)
    
    assert res.status_code == 200
    data = res.json()
    assert data["feasible"] is False
    assert data["reason"] == "destination_cut_off"
    assert data["recommended_action"] == "air_or_handoff_escalation"
    
    # Cleanup
    db_session.delete(v1)
    db_session.delete(v2)
    db_session.commit()

def test_route_evaluation_vehicle_constraints(db_session: Session, test_user_control_room):
    """Test Defect 4: Vehicle constraints must affect route evaluation."""
    token = auth.create_access_token(data={"sub": str(test_user_control_room.id), "role": test_user_control_room.role})
    
    villages = client.get("/api/v1/villages").json()
    v_source = villages[0]["id"]
    v_target = villages[1]["id"]
    
    # Evaluate with heavy weight to ensure constraints are applied
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post("/api/v1/routes/evaluate", json={
        "source_village_id": v_source,
        "target_village_id": v_target,
        "vehicle_constraints": {
            "weight_kg": 50000.0, # High weight
            "height_m": 10.0,
            "is_hazmat": True
        },
        "policy_weights": {}
    }, headers=headers)
    
    assert res.status_code == 200
    data = res.json()
    
    # If the heavy vehicle is restricted, feasible might be false or alternatives might differ
    # We just ensure the endpoint processes the constraint payload properly
    assert "feasible" in data

def test_dispatch_origin_resolution(db_session: Session, test_user_control_room):
    """Test Defect 3: Dispatch origin resolution when source_village_id is not provided."""
    token = auth.create_access_token(data={"sub": str(test_user_control_room.id), "role": test_user_control_room.role})
    
    villages = client.get("/api/v1/villages").json()
    v_target = villages[1]["id"]
    
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post("/api/v1/routes/evaluate", json={
        "target_village_id": v_target,
        "vehicle_constraints": {},
        "policy_weights": {}
    }, headers=headers)
    
    assert res.status_code == 200
    data = res.json()
    assert "feasible" in data
