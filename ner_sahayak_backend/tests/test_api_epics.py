import pytest
import httpx

BASE_URL = "http://localhost:8000"

def post(path, json=None, data=None, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.post(f"{BASE_URL}{path}", json=json, data=data, headers=headers)

def get(path, token=None, params=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.get(f"{BASE_URL}{path}", headers=headers, params=params)

def patch(path, json=None, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.patch(f"{BASE_URL}{path}", json=json, headers=headers)


@pytest.fixture(scope="module")
def control_room_token():
    res = post("/api/v1/auth/login", data={"username": "officer@nersahayak.gov.in", "password": "password123"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def field_officer_token():
    res = post("/api/v1/auth/login", data={"username": "fo@nersahayak.gov.in", "password": "password123"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]


# EPIC 1: Geospatial Foundation

def test_epic1_health_and_auth(field_officer_token):
    assert field_officer_token is not None and len(field_officer_token) > 10


def test_epic1_get_graph_geojson(field_officer_token):
    res = get("/api/v1/roads/geojson", token=field_officer_token)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0


def test_epic1_get_villages(control_room_token):
    res = get("/api/v1/villages", token=control_room_token)
    assert res.status_code == 200, res.text
    assert isinstance(res.json(), list) and len(res.json()) >= 2


# EPIC 2: Multi-Factor Priority

def test_epic2_create_supply_request(field_officer_token, control_room_token):
    villages = get("/api/v1/villages", token=field_officer_token).json()
    village_id = villages[0]["id"]
    fo_users = get("/api/v1/users", token=control_room_token, params={"role": "field_officer"}).json()
    fo_id = fo_users[0]["id"]

    res = post("/api/v1/requests", json={
        "village_id": village_id,
        "requester_id": fo_id,
        "commodity_category": "Medical",
        "commodity": "Paracetamol",
        "quantity": 10,
        "urgency": "critical",
        "stockout_days": 3
    }, token=field_officer_token)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["priority_score"] > 0
    assert "priority_breakdown" in data


def test_epic2_priority_override(control_room_token, field_officer_token):
    villages = get("/api/v1/villages", token=field_officer_token).json()
    village_id = villages[0]["id"]
    fo_users = get("/api/v1/users", token=control_room_token, params={"role": "field_officer"}).json()
    fo_id = fo_users[0]["id"]

    req = post("/api/v1/requests", json={
        "village_id": village_id,
        "requester_id": fo_id,
        "commodity": "Override Test",
        "quantity": 1,
        "urgency": "routine",
        "stockout_days": 0
    }, token=field_officer_token).json()

    override = patch(f"/api/v1/requests/{req['id']}/override", json={
        "new_score": 99.5,
        "override_reason": "Emergency override for test verification"
    }, token=control_room_token)
    assert override.status_code == 200, override.text
    assert override.json()["priority_score"] == 99.5
    assert override.json()["is_overridden"] is True


def test_epic2_unauthorized_override_rejected(field_officer_token):
    res = patch("/api/v1/requests/00000000-0000-0000-0000-000000000000/override",
                json={"new_score": 50.0, "override_reason": "Unauthorized attempt"},
                token=field_officer_token)
    assert res.status_code == 403, f"Expected 403, got {res.status_code}"


# EPIC 4: Environmental Sync (run before Epic 3 to populate probabilities)

def test_epic4_environmental_sync(control_room_token):
    res = post("/api/v1/environmental/sync", token=control_room_token)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "success"


def test_epic4_risk_bands_populated(field_officer_token):
    res = get("/api/v1/roads/geojson", token=field_officer_token)
    features = res.json()["features"]
    with_risk = [f for f in features if f["properties"].get("predicted_risk_band") is not None]
    assert len(with_risk) > 0


# EPIC 3: Route Evaluation & Dispatch

def test_epic3_route_evaluation(control_room_token):
    villages = get("/api/v1/villages", token=control_room_token).json()
    assert len(villages) >= 2

    res = post("/api/v1/routes/evaluate", json={
        "source_village_id": villages[0]["id"],
        "target_village_id": villages[-1]["id"],
        "vehicle_constraints": {},
        "policy_weights": {}
    }, token=control_room_token)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "feasible" in data
    assert "summary" in data
    assert "alternatives" in data


def test_epic3_dispatch_delivery(control_room_token, field_officer_token):
    villages = get("/api/v1/villages", token=control_room_token).json()
    hq_id = villages[0]["id"]
    target_id = villages[-1]["id"]

    fo_users = get("/api/v1/users", token=control_room_token, params={"role": "field_officer"}).json()
    fo_id = fo_users[0]["id"]

    supply_req = post("/api/v1/requests", json={
        "village_id": target_id,
        "requester_id": fo_id,
        "commodity": "Dispatch Test Item",
        "quantity": 1,
        "urgency": "critical",
        "stockout_days": 1
    }, token=field_officer_token).json()

    drivers = get("/api/v1/users", token=control_room_token, params={"role": "driver"}).json()
    assert len(drivers) > 0, "Need at least one seeded driver"
    driver_id = drivers[0]["id"]

    route = post("/api/v1/routes/evaluate", json={
        "source_village_id": hq_id,
        "target_village_id": target_id,
        "vehicle_constraints": {},
        "policy_weights": {}
    }, token=control_room_token).json()

    if not route.get("feasible"):
        pytest.skip("No feasible route in current graph")

    res = post("/api/v1/deliveries", json={
        "supply_request_id": supply_req["id"],
        "driver_id": driver_id,
        "route_plan": {
            "feasible": route["feasible"],
            "summary": route["summary"],
            "constraints_applied": route["constraints_applied"],
            "recommendation": route["recommendation"],
            "alternatives": route["alternatives"],
            "chosen_alternative_index": 0
        }
    }, token=control_room_token)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "dispatched"
    assert res.json()["driver_id"] == driver_id
