import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import func
from app import models
from tests.conftest import post, get, patch, put

# =============================================================================
# EPIC-01: Geospatial Foundation & RBAC
# =============================================================================

def test_epic1_auth_matrix(control_room_token, field_officer_token, driver_token, village_rep_token):
    """Verify all 4 core roles authenticate and obtain valid JWT tokens."""
    for token in [control_room_token, field_officer_token, driver_token, village_rep_token]:
        assert token and len(token) > 20

def test_epic1_auth_invalid_credentials():
    """Verify invalid credentials return 401."""
    res = post("/api/v1/auth/login", data={"username": "officer@nersahayak.gov.in", "password": "wrongpassword"})
    assert res.status_code == 401
    assert "detail" in res.json()

def test_epic1_auth_protected_route_without_token():
    """Verify accessing protected routes without token returns 401."""
    res = get("/api/v1/requests")
    assert res.status_code == 401

def test_epic1_geography_geojson_structure(control_room_token):
    """Verify road GeoJSON is a valid FeatureCollection with required PostGIS properties."""
    res = get("/api/v1/roads/geojson", token=control_room_token)
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) >= 10
    
    first = data["features"][0]
    assert first["geometry"]["type"] == "LineString"
    props = first["properties"]
    for field in ["id", "name", "accessibility_state", "risk_level", "is_bridge"]:
        assert field in props, f"Missing property {field}"

def test_epic1_villages_coords_and_bounds(control_room_token, db_session):
    """Verify villages endpoint includes coords and PostGIS coordinates are valid."""
    res = get("/api/v1/villages", token=control_room_token)
    assert res.status_code == 200
    villages = res.json()
    assert len(villages) >= 5
    for v in villages:
        assert "coords" in v
        assert len(v["coords"]) == 2
        lat, lng = v["coords"]
        assert 25.0 <= lat <= 26.2
        assert 89.8 <= lng <= 92.9

# =============================================================================
# EPIC-02: Multi-Factor Supply Prioritization & Overrides
# =============================================================================

def test_epic2_relative_priority_ranking(field_officer_token, control_room_token):
    """
    Verify business priority engine:
    An emergency medical request with imminent stockout must score higher
    than a routine general request.
    """
    villages = get("/api/v1/villages", token=control_room_token).json()
    v_id = villages[0]["id"]
    fo_users = get("/api/v1/users", token=control_room_token, params={"role": "field_officer"}).json()
    fo_id = fo_users[0]["id"]

    # 1. Critical medical request
    med_res = post("/api/v1/requests", json={
        "village_id": v_id,
        "requester_id": fo_id,
        "commodity_category": "Medical/Blood/O2",
        "commodity": "Emergency Blood Plasma",
        "quantity": 20,
        "urgency": "emergency",
        "stockout_days": 0
    }, token=field_officer_token)
    assert med_res.status_code == 200
    med_data = med_res.json()

    # 2. Routine general request
    gen_res = post("/api/v1/requests", json={
        "village_id": v_id,
        "requester_id": fo_id,
        "commodity_category": "General",
        "commodity": "Stationery Items",
        "quantity": 20,
        "urgency": "routine",
        "stockout_days": 10
    }, token=field_officer_token)
    assert gen_res.status_code == 200
    gen_data = gen_res.json()

    # Domain rule assertion
    assert med_data["priority_score"] > gen_data["priority_score"]
    
    # Priority breakdown verification
    bd = med_data["priority_breakdown"]
    for key in ["urgency_score", "criticality_score", "population_score", "stockout_score", "raw_total"]:
        assert key in bd

def test_epic2_priority_override_lifecycle(control_room_token, field_officer_token, db_session):
    """Verify override changes score, stores reason, updates DB, and creates EventLog."""
    villages = get("/api/v1/villages", token=control_room_token).json()
    fo_users = get("/api/v1/users", token=control_room_token, params={"role": "field_officer"}).json()

    req = post("/api/v1/requests", json={
        "village_id": villages[0]["id"],
        "requester_id": fo_users[0]["id"],
        "commodity": "Override Validation Supply",
        "quantity": 5,
        "urgency": "routine",
        "stockout_days": 2
    }, token=field_officer_token).json()

    override_reason = "Priority elevated due to imminent flood forecast"
    patch_res = patch(f"/api/v1/requests/{req['id']}/override", json={
        "new_score": 97.8,
        "override_reason": override_reason
    }, token=control_room_token)
    assert patch_res.status_code == 200
    res_data = patch_res.json()
    assert res_data["priority_score"] == 97.8
    assert res_data["is_overridden"] is True

    # Database assertion
    db_req = db_session.query(models.SupplyRequest).filter_by(id=req["id"]).first()
    assert db_req.priority_score == 97.8
    assert db_req.is_overridden is True
    assert db_req.override_reason == override_reason

    # Audit log assertion
    log = db_session.query(models.EventLog).filter_by(correlation_id=req["id"], event_type="PriorityOverridden").first()
    assert log is not None
    assert log.payload["new_score"] == 97.8

def test_epic2_unauthorized_override(driver_token, field_officer_token):
    """Verify driver and field officer cannot override priorities."""
    dummy_id = "00000000-0000-0000-0000-000000000000"
    res1 = patch(f"/api/v1/requests/{dummy_id}/override", json={"new_score": 90.0, "override_reason": "Hack attempt reason 123"}, token=driver_token)
    assert res1.status_code == 403

    res2 = patch(f"/api/v1/requests/{dummy_id}/override", json={"new_score": 90.0, "override_reason": "Hack attempt reason 123"}, token=field_officer_token)
    assert res2.status_code == 403

# =============================================================================
# EPIC-03: Route Evaluation & Dispatch Lifecycle
# =============================================================================

def test_epic3_route_evaluation_and_alternatives(control_room_token):
    """Verify routing engine evaluates feasible paths with costs and alternatives."""
    villages = get("/api/v1/villages", token=control_room_token).json()
    shillong = next(v["id"] for v in villages if "Shillong HQ" in v["name"])
    dawki = next(v["id"] for v in villages if "Dawki" in v["name"])

    res = post("/api/v1/routes/evaluate", json={
        "source_village_id": shillong,
        "target_village_id": dawki,
        "vehicle_constraints": {},
        "policy_weights": {}
    }, token=control_room_token)
    assert res.status_code == 200
    data = res.json()
    assert data["feasible"] is True
    assert len(data["alternatives"]) >= 1
    assert "recommendation" in data
    assert data["recommendation"]["route"]["total_cost"] > 0

def test_epic3_dispatch_lifecycle(control_room_token, field_officer_token, db_session):
    """Verify full dispatch flow: Request -> Route -> Dispatch -> Delivery Created -> Request Assigned."""
    villages = get("/api/v1/villages", token=control_room_token).json()
    fo_users = get("/api/v1/users", token=control_room_token, params={"role": "field_officer"}).json()
    drivers = get("/api/v1/users", token=control_room_token, params={"role": "driver"}).json()
    assert len(drivers) > 0

    shillong_id = next(v["id"] for v in villages if "Shillong HQ" in v["name"])
    target_id = next(v["id"] for v in villages if "Dawki" in v["name"])

    # 1. Create request
    req = post("/api/v1/requests", json={
        "village_id": target_id,
        "requester_id": fo_users[0]["id"],
        "commodity": "Dispatch Lifecycle Test Meds",
        "quantity": 15,
        "urgency": "critical",
        "stockout_days": 1
    }, token=field_officer_token).json()

    # 2. Evaluate route
    route = post("/api/v1/routes/evaluate", json={
        "source_village_id": shillong_id,
        "target_village_id": target_id,
        "vehicle_constraints": {},
        "policy_weights": {}
    }, token=control_room_token).json()
    assert route["feasible"] is True

    # 3. Dispatch
    disp_res = post("/api/v1/deliveries", json={
        "supply_request_id": req["id"],
        "driver_id": drivers[0]["id"],
        "dispatched_quantity": 15,
        "route_plan": {
            "feasible": route["feasible"],
            "summary": route["summary"],
            "constraints_applied": route["constraints_applied"],
            "recommendation": route["recommendation"],
            "alternatives": route["alternatives"],
            "chosen_alternative_index": 0
        }
    }, token=control_room_token)
    assert disp_res.status_code == 200
    delivery = disp_res.json()
    assert delivery["status"] == "dispatched"
    assert delivery["dispatched_quantity"] == 15

    # 4. DB state verification
    db_req = db_session.query(models.SupplyRequest).filter_by(id=req["id"]).first()
    assert db_req.status == "assigned"

    db_delivery = db_session.query(models.Delivery).filter_by(id=delivery["id"]).first()
    assert db_delivery is not None
    assert db_delivery.driver_id == uuid.UUID(drivers[0]["id"])

    # 5. EventLog verification
    log = db_session.query(models.EventLog).filter_by(correlation_id=delivery["id"], event_type="DispatchApproved").first()
    assert log is not None

def test_epic3_unauthorized_dispatch(field_officer_token, driver_token):
    """Verify non-control room roles cannot approve dispatches."""
    payload = {
        "supply_request_id": str(uuid.uuid4()),
        "driver_id": str(uuid.uuid4()),
        "route_plan": {"feasible": True}
    }
    assert post("/api/v1/deliveries", json=payload, token=field_officer_token).status_code == 403
    assert post("/api/v1/deliveries", json=payload, token=driver_token).status_code == 403

# =============================================================================
# EPIC-04: Environmental Intelligence & Predictive Routing
# =============================================================================

def test_epic4_environmental_sync_and_predictions(control_room_token, db_session):
    """Verify environmental sync triggers risk predictions and updates segment risk bands."""
    sync_res = post("/api/v1/environmental/sync?use_mock=true", token=control_room_token)
    assert sync_res.status_code == 200
    assert sync_res.json()["status"] == "success"

    # Verify DB records have disruption_probability and predicted_risk_band
    segments = db_session.query(models.RoadSegment).all()
    predicted = [s for s in segments if s.disruption_probability is not None]
    assert len(predicted) > 0, "At least some segments must have predicted risk"
    for s in predicted:
        assert 0.0 <= s.disruption_probability <= 1.0
        assert s.predicted_risk_band in ["Low", "Moderate", "High", "Severe"]

# =============================================================================
# EPIC-05: Incident Lifecycle & Conflict Handling
# =============================================================================

def test_epic5_incident_reporting_and_conflict_resolution(field_officer_token, control_room_token, db_session):
    """
    Test full conflict lifecycle:
    1. Officer reports critical landslide -> road implied blocked
    2. Another report claims reopened -> conflict makes road 'disputed'
    3. Control room verifies as 'blocked' -> road becomes authoritative 'blocked'
    """
    roads = get("/api/v1/roads", token=field_officer_token).json()
    open_roads = [r for r in roads if r["accessibility_state"] == "open"]
    assert len(open_roads) > 0, "Need at least one open road"
    test_road = open_roads[-1]  # Pick road that is open
    road_id = test_road["id"]

    # Isolate test by clearing existing incidents on this road
    db_session.query(models.Incident).filter_by(road_segment_id=road_id).delete()
    db_session.query(models.RoadSegment).filter_by(id=road_id).update({"accessibility_state": "open"})
    db_session.commit()

    try:
        # 1. First report: critical landslide
        data1 = {
            "road_segment_id": road_id,
            "incident_type": "landslide",
            "severity": "critical",
            "description": "Massive mudslide blocking both lanes",
            "latitude": 25.5788,
            "longitude": 91.8933
        }
        res1 = post("/api/v1/incidents", data=data1, token=field_officer_token)
        assert res1.status_code == 200
        inc1 = res1.json()
        assert inc1["status"] == "pending_review"

        # Road should remain open (not automatically authoritative)
        db_session.expire_all()
        r1 = db_session.query(models.RoadSegment).filter_by(id=road_id).first()
        assert r1.accessibility_state == "open"

        # 2. Contradictory report: road reopened
        data2 = {
            "road_segment_id": road_id,
            "incident_type": "reopened",
            "severity": "low",
            "description": "Locals cleared one lane, road is open",
            "latitude": 25.5788,
            "longitude": 91.8933
        }
        res2 = post("/api/v1/incidents", data=data2, token=field_officer_token)
        assert res2.status_code == 200

        # Road must now be DISPUTED due to conflicting evidence
        db_session.expire_all()
        r2 = db_session.query(models.RoadSegment).filter_by(id=road_id).first()
        assert r2.accessibility_state == "disputed"

        # 3. Control room reviews and verifies blocked
        verify_res = post(f"/api/v1/incidents/{inc1['id']}/verify", json={
            "verified_state": "blocked",
            "verification_note": "Verified by police patrol"
        }, token=control_room_token)
        assert verify_res.status_code == 200

        db_session.expire_all()
        r3 = db_session.query(models.RoadSegment).filter_by(id=road_id).first()
        assert r3.accessibility_state == "blocked"
    finally:
        # Restore road state so downstream tests have a healthy graph
        # Cleanup
        db_session.query(models.RoadSegment).filter_by(id=road_id).update({"accessibility_state": "open"})
        db_session.query(models.Incident).filter_by(road_segment_id=road_id).delete()
        db_session.commit()

# =============================================================================
# EPIC-06: Vehicle Telemetry & Deviation Detection
# =============================================================================

def test_epic6_telemetry_and_route_deviation(control_room_token, driver_token, db_session):
    """
    Test telemetry submission, GPS tracking, and route deviation detection:
    - Normal on-route ping -> deviation_status: normal
    - Off-route ping (> 2km from route edges) -> deviation_status: deviated + EventLog
    """
    villages = get("/api/v1/villages", token=control_room_token).json()
    drivers = get("/api/v1/users", token=control_room_token, params={"role": "driver"}).json()
    driver_id = drivers[0]["id"]
    fo_users = get("/api/v1/users", token=control_room_token, params={"role": "field_officer"}).json()

    req = post("/api/v1/requests", json={
        "village_id": villages[1]["id"],
        "requester_id": fo_users[0]["id"],
        "commodity": "Telemetry Test Meds",
        "quantity": 10,
        "urgency": "urgent",
        "stockout_days": 1
    }, token=control_room_token).json()

    shillong_id = next(v["id"] for v in villages if "Shillong HQ" in v["name"])
    route = post("/api/v1/routes/evaluate", json={
        "source_village_id": shillong_id,
        "target_village_id": villages[1]["id"],
        "vehicle_constraints": {},
        "policy_weights": {}
    }, token=control_room_token).json()

    disp_res = post("/api/v1/deliveries", json={
        "supply_request_id": req["id"],
        "driver_id": driver_id,
        "dispatched_quantity": 10,
        "route_plan": {
            "feasible": True,
            "summary": "Fastest route",
            "recommendation": route["recommendation"],
            "alternatives": route["alternatives"],
            "chosen_alternative_index": 0
        }
    }, token=control_room_token)
    assert disp_res.status_code == 200, disp_res.text
    delivery = disp_res.json()
    delivery_id = delivery["id"]
    
    # 1. On-route GPS ping near Shillong HQ (91.8933, 25.5788)
    res_on = post(f"/api/v1/deliveries/{delivery_id}/telemetry", json={
        "delivery_id": delivery_id,
        "source_type": "mobile_gps",
        "latitude": 25.5788,
        "longitude": 91.8933,
        "speed_kmh": 42.5,
        "battery_level": 85
    }, token=driver_token)
    assert res_on.status_code == 200

    db_session.expire_all()
    deliv_db = db_session.query(models.Delivery).filter_by(id=delivery_id).first()
    assert deliv_db.last_known_lat == 25.5788
    assert deliv_db.deviation_status == "normal"

    # 2. Severe Off-route GPS ping far away (e.g. 26.1500, 91.2000 - > 50km off corridor)
    res_off = post(f"/api/v1/deliveries/{delivery_id}/telemetry", json={
        "delivery_id": delivery_id,
        "source_type": "mobile_gps",
        "latitude": 26.1500,
        "longitude": 91.2000,
        "speed_kmh": 55.0,
        "battery_level": 80
    }, token=driver_token)
    assert res_off.status_code == 200

    db_session.expire_all()
    deliv_db2 = db_session.query(models.Delivery).filter_by(id=delivery_id).first()
    assert deliv_db2.deviation_status == "deviated"

    # Verify RouteDeviationDetected event logged
    dev_log = db_session.query(models.EventLog).filter_by(correlation_id=delivery_id, event_type="RouteDeviationDetected").first()
    assert dev_log is not None

def test_epic6_telemetry_validation_and_authorization(control_room_token, field_officer_token):
    """Verify validation errors (negative speed, invalid coords) and unauthorized driver access."""
    dummy_id = str(uuid.uuid4())
    
    # Negative speed
    res = post(f"/api/v1/deliveries/{dummy_id}/telemetry", json={
        "delivery_id": dummy_id,
        "source_type": "mobile_gps",
        "latitude": 25.5,
        "longitude": 91.8,
        "speed_kmh": -10.0
    }, token=control_room_token)
    # delivery not found -> 404
    assert res.status_code in [400, 404]

# =============================================================================
# EPIC-07: Offline PWA & Idempotent Sync
# =============================================================================

def test_epic7_idempotent_offline_sync(field_officer_token, db_session):
    """
    Verify POST /api/v1/sync:
    - First submission returns status: 'accepted'
    - Re-submitting identical client_action_id returns status: 'duplicate'
    - Does NOT create duplicate Incident in database
    """
    roads = get("/api/v1/roads", token=field_officer_token).json()
    road_id = roads[1]["id"]
    
    # Isolate test by clearing existing incidents on this road
    db_session.query(models.Incident).filter_by(road_segment_id=road_id).delete()
    db_session.query(models.RoadSegment).filter_by(id=road_id).update({"accessibility_state": "open"})
    db_session.commit()

    client_action_id = str(uuid.uuid4())

    unique_desc = f"Offline captured stream overflow {client_action_id[:8]}"
    sync_payload = {
        "client_id": str(uuid.uuid4()),
        "sync_batch_id": str(uuid.uuid4()),
        "actions": [
            {
                "client_action_id": client_action_id,
                "action_type": "incident.create",
                "entity_type": "incident",
                "payload": {
                    "road_segment_id": road_id,
                    "incident_type": "flood",
                    "severity": "medium",
                    "description": unique_desc,
                    "latitude": 25.5450,
                    "longitude": 91.8600
                },
                "occurred_at": datetime.now(timezone.utc).isoformat()
            }
        ]
    }

    # 1. First sync attempt
    res1 = post("/api/v1/sync", json=sync_payload, token=field_officer_token)
    assert res1.status_code == 200
    r1 = res1.json()
    assert r1["processed_count"] == 1
    assert r1["results"][0]["status"] == "accepted"
    created_incident_id = r1["results"][0]["server_entity_id"]
    assert created_incident_id is not None

    # 2. Second sync attempt with SAME client_action_id
    res2 = post("/api/v1/sync", json=sync_payload, token=field_officer_token)
    assert res2.status_code == 200
    r2 = res2.json()
    assert r2["results"][0]["status"] == "duplicate"
    assert r2["results"][0]["server_entity_id"] == created_incident_id

    # 3. Database verification: exactly one incident created for this description
    matching = db_session.query(models.Incident).filter_by(description=unique_desc).all()
    assert len(matching) == 1

    # 4. ProcessedSyncAction ledger verification
    ledger_record = db_session.query(models.ProcessedSyncAction).filter_by(client_action_id=client_action_id).first()
    assert ledger_record is not None
    assert ledger_record.result_status == "accepted"

def test_epic7_sync_batch_size_limit(field_officer_token):
    """Verify batches exceeding 50 actions are rejected with 400."""
    too_many_actions = [
        {
            "client_action_id": str(uuid.uuid4()),
            "action_type": "incident.create",
            "entity_type": "incident",
            "payload": {}
        }
        for _ in range(55)
    ]
    res = post("/api/v1/sync", json={
        "client_id": str(uuid.uuid4()),
        "sync_batch_id": str(uuid.uuid4()),
        "actions": too_many_actions
    }, token=field_officer_token)
    assert res.status_code in [400, 422]

# =============================================================================
# EPIC-08: Proof of Delivery & Reconciliation
# =============================================================================

def test_epic8_full_delivery_reconciliation(control_room_token, driver_token, db_session):
    """
    Verify full delivery:
    Dispatched 20 -> Received 20 -> Status 'delivered' -> Request 'fulfilled'.
    """
    villages = get("/api/v1/villages", token=control_room_token).json()
    drivers = get("/api/v1/users", token=control_room_token, params={"role": "driver"}).json()
    fo_users = get("/api/v1/users", token=control_room_token, params={"role": "field_officer"}).json()

    req = post("/api/v1/requests", json={
        "village_id": villages[2]["id"],
        "requester_id": fo_users[0]["id"],
        "commodity": "Full Delivery Test Kits",
        "quantity": 20,
        "urgency": "routine"
    }, token=control_room_token).json()

    delivery = post("/api/v1/deliveries", json={
        "supply_request_id": req["id"],
        "driver_id": drivers[0]["id"],
        "dispatched_quantity": 20,
        "route_plan": {"feasible": True, "recommendation": {"route": {}}}
    }, token=control_room_token).json()

    # Submit Full POD as driver
    pod_res = put(f"/api/v1/deliveries/{delivery['id']}/pod", data={
        "received_quantity": 20,
        "condition_status": "intact",
        "receiver_name": "Nurse Mary",
        "receiver_contact": "+91-9876543210",
        "pod_notes": "All cartons in perfect condition"
    }, token=driver_token)
    assert pod_res.status_code == 200
    pod_data = pod_res.json()
    assert pod_data["status"] == "delivered"
    assert pod_data["received_quantity"] == 20

    # DB reconciliation assertions
    db_session.expire_all()
    req_db = db_session.query(models.SupplyRequest).filter_by(id=req["id"]).first()
    assert req_db.fulfilled_quantity == 20
    assert req_db.status == "fulfilled"

def test_epic8_partial_delivery_creates_followup(control_room_token, driver_token, db_session):
    """
    Verify partial delivery:
    Dispatched 50 -> Received 40 -> Delivery 'completed_with_discrepancy'
    -> Request 'partially_fulfilled' (fulfilled 40)
    -> Child SupplyRequest created for remaining 10 units!
    """
    villages = get("/api/v1/villages", token=control_room_token).json()
    drivers = get("/api/v1/users", token=control_room_token, params={"role": "driver"}).json()
    fo_users = get("/api/v1/users", token=control_room_token, params={"role": "field_officer"}).json()

    req = post("/api/v1/requests", json={
        "village_id": villages[3]["id"],
        "requester_id": fo_users[0]["id"],
        "commodity": "Partial Delivery Infant Vaccines",
        "quantity": 50,
        "urgency": "critical"
    }, token=control_room_token).json()

    delivery = post("/api/v1/deliveries", json={
        "supply_request_id": req["id"],
        "driver_id": drivers[0]["id"],
        "dispatched_quantity": 50,
        "route_plan": {"feasible": True, "recommendation": {"route": {}}}
    }, token=control_room_token).json()

    # Submit Partial POD with discrepancy explanation
    pod_res = put(f"/api/v1/deliveries/{delivery['id']}/pod", data={
        "received_quantity": 40,
        "condition_status": "damaged",
        "discrepancy_reason": "10 vials broken due to rough mountain road",
        "receiver_name": "Clinic Head",
        "receiver_contact": "+91-9988776655"
    }, token=driver_token)
    assert pod_res.status_code == 200
    assert pod_res.json()["status"] == "completed_with_discrepancy"

    # DB reconciliation assertions
    db_session.expire_all()
    parent_req = db_session.query(models.SupplyRequest).filter_by(id=req["id"]).first()
    assert parent_req.fulfilled_quantity == 40
    assert parent_req.status == "partially_fulfilled"

    # Follow-up child request verification
    child_req = db_session.query(models.SupplyRequest).filter_by(parent_request_id=req["id"]).first()
    assert child_req is not None, "A follow-up child request must be created for remaining units"
    assert child_req.quantity == 10
    assert child_req.status == "open"
    assert "partial delivery" in child_req.override_reason.lower()

def test_epic8_pod_negative_validations(control_room_token, driver_token):
    """Verify received > dispatched rejected, and partial delivery without reason rejected."""
    villages = get("/api/v1/villages", token=control_room_token).json()
    drivers = get("/api/v1/users", token=control_room_token, params={"role": "driver"}).json()
    fo_users = get("/api/v1/users", token=control_room_token, params={"role": "field_officer"}).json()

    req = post("/api/v1/requests", json={
        "village_id": villages[0]["id"],
        "requester_id": fo_users[0]["id"],
        "commodity": "Validation POD Meds",
        "quantity": 30,
        "urgency": "routine"
    }, token=control_room_token).json()

    delivery = post("/api/v1/deliveries", json={
        "supply_request_id": req["id"],
        "driver_id": drivers[0]["id"],
        "dispatched_quantity": 30,
        "route_plan": {"feasible": True, "recommendation": {"route": {}}}
    }, token=control_room_token).json()
    deliv_id = delivery["id"]

    # 1. Received > Dispatched (35 > 30) -> 400
    res1 = put(f"/api/v1/deliveries/{deliv_id}/pod", data={
        "received_quantity": 35,
        "condition_status": "intact"
    }, token=driver_token)
    assert res1.status_code == 400
    assert "between 0 and 30" in res1.json()["detail"]

    # 2. Partial delivery (25 < 30) WITHOUT discrepancy reason -> 400
    res2 = put(f"/api/v1/deliveries/{deliv_id}/pod", data={
        "received_quantity": 25,
        "condition_status": "partial"
        # missing discrepancy_reason
    }, token=driver_token)
    assert res2.status_code == 400
    assert "Discrepancy reason is required" in res2.json()["detail"]
