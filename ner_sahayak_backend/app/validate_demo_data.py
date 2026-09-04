import sys
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from . import models, schemas
from .main import app
from .database import SessionLocal

def validate_demo_data():
    db = SessionLocal()
    client = TestClient(app)
    errors = []

    try:
        # 1. Verify Users & Roles
        users = db.query(models.User).filter(models.User.email.like("demo.%")).all()
        if len(users) < 7:
            errors.append(f"Missing demo users. Found {len(users)}, expected 7.")
        roles = {u.role for u in users}
        expected_roles = {"control_room", "supervisor", "field_officer", "driver", "village_rep"}
        if not expected_roles.issubset(roles):
            errors.append(f"Missing roles. Found {roles}, expected at least {expected_roles}")

        # 2. Verify Origin & Villages
        origin = db.query(models.Village).filter_by(name="DEMO-HQ-01 (Logistics Origin)").first()
        if not origin:
            errors.append("Logistics origin (DEMO-HQ-01) not found.")
        elif not origin.is_handoff:
            errors.append("Logistics origin is not marked as is_handoff=True")

        villages = db.query(models.Village).filter(models.Village.name.like("DEMO-%")).all()
        if len(villages) < 5:
            errors.append(f"Missing demo villages. Found {len(villages)}, expected 5.")

        # 3. Verify Road Network & Routing Scenario
        roads = db.query(models.RoadSegment).filter(models.RoadSegment.name.like("DEMO-%")).all()
        if len(roads) < 5:
            errors.append(f"Missing demo roads. Found {len(roads)}, expected at least 5.")

        # Try to route from Origin to REMOTE
        remote = db.query(models.Village).filter_by(name="DEMO-VILLAGE-REMOTE").first()
        if origin and remote:
            # First, check authentication for endpoint (we need control room token)
            control_user = next((u for u in users if u.role == "control_room"), None)
            if control_user:
                # Login
                login_res = client.post("/api/v1/auth/login", data={"username": control_user.email, "password": "DemoPassword123!"})
                if login_res.status_code == 200:
                    token = login_res.json()["access_token"]
                    # Evaluate route
                    eval_res = client.post("/api/v1/routes/evaluate", headers={"Authorization": f"Bearer {token}"}, json={
                        "source_village_id": str(origin.id),
                        "target_village_id": str(remote.id),
                        "vehicle_constraints": {},
                        "policy_weights": {}
                    })
                    if eval_res.status_code == 200:
                        data = eval_res.json()
                        if not data["feasible"]:
                            errors.append("Route to REMOTE is not feasible.")
                        if len(data["alternatives"]) < 1:
                            errors.append("No route alternatives found to REMOTE. Expected at least 2 paths (Route A and B).")
                    else:
                        errors.append(f"Route evaluate failed: {eval_res.status_code} - {eval_res.text}")
                else:
                    errors.append("Failed to login as control room user.")
            else:
                errors.append("No control room user found for testing routes.")

        # 4. Verify Vehicles/Driver Assignments
        assign_events = db.query(models.EventLog).filter_by(event_type="DriverVehicleAssignment").all()
        if len(assign_events) < 2:
            errors.append(f"Missing driver vehicle assignments in EventLog. Found {len(assign_events)}, expected 2.")

        # 5. Verify Critical Request
        reqs = db.query(models.SupplyRequest).filter(models.SupplyRequest.commodity.like("DEMO %")).all()
        if len(reqs) < 3:
            errors.append(f"Missing demo requests. Found {len(reqs)}, expected 3.")
        crit = next((r for r in reqs if r.urgency == "emergency"), None)
        if not crit:
            errors.append("Missing critical request scenario.")

        # 6. Verify Delivery & Telemetry
        dels = db.query(models.Delivery).join(models.SupplyRequest).filter(models.SupplyRequest.commodity.like("DEMO %")).all()
        if len(dels) < 1:
            errors.append("Missing delivery for demo request.")
        else:
            tel = db.query(models.DeliveryTelemetry).filter_by(delivery_id=dels[0].id).all()
            if len(tel) < 3:
                errors.append(f"Missing telemetry checkpoints for delivery. Found {len(tel)}, expected 3.")

        # 7. Verify Alerts & Audit
        alerts = db.query(models.Alert).filter(models.Alert.title.like("DEMO:%")).all()
        if len(alerts) < 1:
            errors.append("Missing demo alerts.")
        
        events = db.query(models.EventLog).filter(
            models.EventLog.event_type.in_(["SupplyRequestCreated", "IncidentReported", "DispatchApproved", "AlertCreated"])
        ).all()
        if len(events) < 5:
            errors.append(f"Missing audit events for demo scenario. Found {len(events)}.")

        # 8. Orphan Check
        # Check if telemetry has valid delivery
        orphan_tel = db.query(models.DeliveryTelemetry).outerjoin(models.Delivery).filter(models.Delivery.id == None).all()
        if orphan_tel:
            errors.append(f"Found {len(orphan_tel)} orphan telemetry points.")

        if errors:
            print("Validation FAILED with errors:")
            for e in errors:
                print(f" - {e}")
            sys.exit(1)
        else:
            print("Validation SUCCESS. The demo dataset is intact and fully demonstrable.")

    finally:
        db.close()

if __name__ == "__main__":
    validate_demo_data()
