import sys
import os
import pytest
import httpx
from sqlalchemy.orm import Session

# Ensure /app is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app import models

BASE_URL = "http://localhost:8000"

def post(path, json=None, data=None, token=None, files=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.post(f"{BASE_URL}{path}", json=json, data=data, headers=headers, files=files)

def get(path, token=None, params=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.get(f"{BASE_URL}{path}", headers=headers, params=params)

def patch(path, json=None, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.patch(f"{BASE_URL}{path}", json=json, headers=headers)

def put(path, json=None, data=None, token=None, files=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.put(f"{BASE_URL}{path}", json=json, data=data, headers=headers, files=files)

@pytest.fixture(scope="session")
def db_session():
    """Provides a direct database session for PostGIS and DB integrity assertions."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture(scope="session")
def control_room_token():
    res = post("/api/v1/auth/login", data={"username": "officer@nersahayak.gov.in", "password": "password123"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]

@pytest.fixture(scope="session")
def field_officer_token():
    res = post("/api/v1/auth/login", data={"username": "fo@nersahayak.gov.in", "password": "password123"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]

@pytest.fixture(scope="session")
def driver_token():
    res = post("/api/v1/auth/login", data={"username": "driver@nersahayak.gov.in", "password": "driver123"})
    assert res.status_code == 200, f"Driver login failed: {res.text}"
    return res.json()["access_token"]

@pytest.fixture(scope="session")
def village_rep_token():
    res = post("/api/v1/auth/login", data={"username": "hospital@nersahayak.gov.in", "password": "hospital123"})
    assert res.status_code == 200, f"Village rep login failed: {res.text}"
    return res.json()["access_token"]
