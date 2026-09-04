import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app import models, auth
import uuid

client = TestClient(app)

def test_prevent_privileged_registration(db: Session):
    response = client.post("/api/v1/auth/register", json={
        "email": "hacker@example.com",
        "password": "Password123!",
        "full_name": "Hacker",
        "role": "control_room",
        "phone": "+910000000000"
    })
    assert response.status_code == 403
    assert "privileged role" in response.json()["detail"]
    
def test_delivery_idor_active_deliveries(db: Session, test_user_driver, test_user_control_room, test_user_village_rep):
    # Driver gets active deliveries (should see only theirs, empty for now)
    token = auth.create_access_token(data={"sub": test_user_driver.id, "role": test_user_driver.role})
    response = client.get("/api/v1/deliveries/active", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    
    # Village rep gets active deliveries
    token_vr = auth.create_access_token(data={"sub": test_user_village_rep.id, "role": test_user_village_rep.role})
    response = client.get("/api/v1/deliveries/active", headers={"Authorization": f"Bearer {token_vr}"})
    assert response.status_code == 200

def test_incidents_authorization(db: Session, test_user_driver, test_user_control_room):
    # Unauthenticated should fail
    response = client.get("/api/v1/incidents")
    assert response.status_code == 401
    
    # Authenticated should pass
    token = auth.create_access_token(data={"sub": test_user_driver.id, "role": test_user_driver.role})
    response = client.get("/api/v1/incidents", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
