import sys
import argparse
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from geoalchemy2.elements import WKTElement

from . import models, auth
from .database import SessionLocal

# Deterministic namespace for demo data
DEMO_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "demo.nersahayak.local")

def get_demo_uuid(name: str) -> uuid.UUID:
    return uuid.uuid5(DEMO_NAMESPACE, name)

def delete_by_ids(db: Session, model, ids):
    if ids:
        db.query(model).filter(model.id.in_(ids)).delete(synchronize_session=False)

def reset_demo_data(db: Session):
    print("Cleaning up previous demo data...")
    # Find demo users
    demo_users = db.query(models.User).filter(models.User.email.like("demo.%")).all()
    user_ids = [u.id for u in demo_users]

    # Find demo villages
    demo_villages = db.query(models.Village).filter(models.Village.name.like("DEMO-%")).all()
    village_ids = [v.id for v in demo_villages]

    # Find demo roads
    demo_roads = db.query(models.RoadSegment).filter(models.RoadSegment.name.like("DEMO-%")).all()
    road_ids = [r.id for r in demo_roads]

    # Find demo requests (where requester is a demo user)
    demo_requests = db.query(models.SupplyRequest).filter(models.SupplyRequest.requester_id.in_(user_ids)).all() if user_ids else []
    request_ids = [r.id for r in demo_requests]

    # Deliveries
    demo_deliveries = db.query(models.Delivery).filter(models.Delivery.driver_id.in_(user_ids)).all() if user_ids else []
    delivery_ids = [d.id for d in demo_deliveries]

    # Delete Telemetry
    if delivery_ids:
        db.query(models.DeliveryTelemetry).filter(models.DeliveryTelemetry.delivery_id.in_(delivery_ids)).delete(synchronize_session=False)

    # Delete EventLogs
    if user_ids or delivery_ids or request_ids:
        db.query(models.EventLog).filter(
            (models.EventLog.actor_id.in_(user_ids)) |
            (models.EventLog.correlation_id.in_(delivery_ids + request_ids))
        ).delete(synchronize_session=False)

    # Delete Alerts
    if request_ids or delivery_ids:
        db.query(models.Alert).filter(
            (models.Alert.related_request_id.in_(request_ids)) |
            (models.Alert.related_delivery_id.in_(delivery_ids))
        ).delete(synchronize_session=False)

    # Delete Incidents
    if user_ids:
        db.query(models.Incident).filter(models.Incident.reporter_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(models.ProcessedSyncAction).filter(models.ProcessedSyncAction.user_id.in_(user_ids)).delete(synchronize_session=False)

    delete_by_ids(db, models.Delivery, delivery_ids)
    delete_by_ids(db, models.SupplyRequest, request_ids)
    
    if road_ids:
        db.query(models.SegmentFeature).filter(models.SegmentFeature.road_segment_id.in_(road_ids)).delete(synchronize_session=False)
    
    delete_by_ids(db, models.RoadSegment, road_ids)
    delete_by_ids(db, models.Village, village_ids)
    delete_by_ids(db, models.User, user_ids)
    
    db.commit()
    print("Demo data cleanup complete.")

def seed_demo_data(db: Session):
    print("Seeding demo data...")
    password = auth.get_password_hash("DemoPassword123!")
    now = datetime.now(timezone.utc)

    # --- 1. USERS ---
    users = [
        models.User(id=get_demo_uuid("user_control"), name="Demo Control Room", role="control_room", email="demo.control@ner-sahayak.local", hashed_password=password, district="East Khasi Hills"),
        models.User(id=get_demo_uuid("user_super"), name="Demo Supervisor", role="supervisor", email="demo.supervisor@ner-sahayak.local", hashed_password=password, district="East Khasi Hills"),
        models.User(id=get_demo_uuid("user_field"), name="Demo Field Officer", role="field_officer", email="demo.field@ner-sahayak.local", hashed_password=password, district="East Khasi Hills"),
        models.User(id=get_demo_uuid("user_d1"), name="Demo Driver 1 (Heavy Truck)", role="driver", email="demo.driver1@ner-sahayak.local", hashed_password=password, district="East Khasi Hills"),
        models.User(id=get_demo_uuid("user_d2"), name="Demo Driver 2 (Light Van)", role="driver", email="demo.driver2@ner-sahayak.local", hashed_password=password, district="East Khasi Hills"),
        models.User(id=get_demo_uuid("user_d3"), name="Demo Driver 3 (Special)", role="driver", email="demo.driver3@ner-sahayak.local", hashed_password=password, district="East Khasi Hills"),
        models.User(id=get_demo_uuid("user_rep"), name="Demo Village Rep", role="village_rep", email="demo.village@ner-sahayak.local", hashed_password=password, district="East Khasi Hills")
    ]
    db.add_all(users)
    db.commit()

    # Log vehicle assignments to Audit log
    db.add(models.EventLog(
        event_id=get_demo_uuid("evt_assign_d1"), event_type="DriverVehicleAssignment",
        actor_id=get_demo_uuid("user_super"), correlation_id=get_demo_uuid("user_d1"),
        payload={"vehicle_type": "relief_truck", "weight_kg": 8000, "height_m": 3.5, "hazmat": False},
        occurred_at=now - timedelta(days=1)
    ))
    db.add(models.EventLog(
        event_id=get_demo_uuid("evt_assign_d2"), event_type="DriverVehicleAssignment",
        actor_id=get_demo_uuid("user_super"), correlation_id=get_demo_uuid("user_d2"),
        payload={"vehicle_type": "light_vehicle", "weight_kg": 2500, "height_m": 2.2, "hazmat": False},
        occurred_at=now - timedelta(days=1)
    ))
    db.commit()

    # --- 2. GEOGRAPHY (VILLAGES) ---
    coords = {
        "HQ": (91.8933, 25.5788),      # Shillong
        "NEAR": (91.8600, 25.5450),    # Upper Shillong
        "MOD": (91.8540, 25.5140),     # Mylliem
        "REMOTE": (91.7166, 25.2815),  # Cherrapunji
        "DIFF": (91.6850, 25.3520)     # Weiloi
    }
    
    villages = [
        models.Village(id=get_demo_uuid("vill_hq"), name="DEMO-HQ-01 (Logistics Origin)", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["HQ"][0]} {coords["HQ"][1]})', srid=4326), population=100000, is_handoff=True),
        models.Village(id=get_demo_uuid("vill_near"), name="DEMO-VILLAGE-NEAR", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["NEAR"][0]} {coords["NEAR"][1]})', srid=4326), population=5000),
        models.Village(id=get_demo_uuid("vill_mod"), name="DEMO-VILLAGE-MOD", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["MOD"][0]} {coords["MOD"][1]})', srid=4326), population=3200),
        models.Village(id=get_demo_uuid("vill_remote"), name="DEMO-VILLAGE-REMOTE", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["REMOTE"][0]} {coords["REMOTE"][1]})', srid=4326), population=15000),
        models.Village(id=get_demo_uuid("vill_diff"), name="DEMO-VILLAGE-DIFF", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["DIFF"][0]} {coords["DIFF"][1]})', srid=4326), population=1200)
    ]
    db.add_all(villages)
    db.commit()

    # --- 3. ROAD NETWORK ---
    def make_line(u, v):
        return WKTElement(f'LINESTRING({coords[u][0]} {coords[u][1]}, {coords[v][0]} {coords[v][1]})', srid=4326)

    roads = [
        models.RoadSegment(id=get_demo_uuid("road_hq_near"), name="DEMO-ROAD-HQ-NEAR", source_id=get_demo_uuid("vill_hq"), target_id=get_demo_uuid("vill_near"), geom=make_line("HQ", "NEAR"), distance_km=8.0, base_travel_time_min=20.0, road_type="primary"),
        models.RoadSegment(id=get_demo_uuid("road_near_mod"), name="DEMO-ROAD-NEAR-MOD", source_id=get_demo_uuid("vill_near"), target_id=get_demo_uuid("vill_mod"), geom=make_line("NEAR", "MOD"), distance_km=7.5, base_travel_time_min=15.0, road_type="primary"),
        models.RoadSegment(id=get_demo_uuid("road_mod_diff"), name="DEMO-ROAD-MOD-DIFF", source_id=get_demo_uuid("vill_mod"), target_id=get_demo_uuid("vill_diff"), geom=make_line("MOD", "DIFF"), distance_km=15.0, base_travel_time_min=35.0, road_type="secondary"),
        # Route A to REMOTE (Short but weight restricted)
        models.RoadSegment(id=get_demo_uuid("road_diff_remote_A"), name="DEMO-ROUTE-A-REMOTE", source_id=get_demo_uuid("vill_diff"), target_id=get_demo_uuid("vill_remote"), geom=make_line("DIFF", "REMOTE"), distance_km=10.0, base_travel_time_min=25.0, road_type="tertiary", is_bridge=True, max_vehicle_weight_kg=3000.0),
        # Route B to REMOTE (Long but no weight restriction)
        models.RoadSegment(id=get_demo_uuid("road_mod_remote_B"), name="DEMO-ROUTE-B-REMOTE", source_id=get_demo_uuid("vill_mod"), target_id=get_demo_uuid("vill_remote"), geom=make_line("MOD", "REMOTE"), distance_km=25.0, base_travel_time_min=60.0, road_type="primary", is_bridge=False, risk_level=0.2)
    ]
    db.add_all(roads)
    db.commit()

    # Environmental Feature on Route B
    db.add(models.SegmentFeature(
        id=get_demo_uuid("feat_b"), road_segment_id=get_demo_uuid("road_mod_remote_B"),
        features_json={"soil_moisture": 0.8, "rainfall_24h": 120, "slope_instability": True},
        captured_at=now
    ))
    db.commit()

    # --- 4. SUPPLY REQUESTS ---
    req_critical = models.SupplyRequest(
        id=get_demo_uuid("req_crit"), village_id=get_demo_uuid("vill_remote"), requester_id=get_demo_uuid("user_rep"),
        commodity_category="Medical/Blood/O2", commodity="DEMO Critical Plasma", quantity=10, urgency="emergency", stockout_days=0,
        priority_score=98.5, status="open", created_at=now - timedelta(hours=2)
    )
    req_high = models.SupplyRequest(
        id=get_demo_uuid("req_high"), village_id=get_demo_uuid("vill_diff"), requester_id=get_demo_uuid("user_rep"),
        commodity_category="Food/Water", commodity="DEMO Emergency Rations", quantity=100, urgency="urgent", stockout_days=2,
        priority_score=75.0, status="open", created_at=now - timedelta(hours=3)
    )
    req_normal = models.SupplyRequest(
        id=get_demo_uuid("req_norm"), village_id=get_demo_uuid("vill_near"), requester_id=get_demo_uuid("user_rep"),
        commodity_category="General", commodity="DEMO Blankets", quantity=50, urgency="routine", stockout_days=0,
        priority_score=35.0, status="open", created_at=now - timedelta(hours=5)
    )
    req_transit = models.SupplyRequest(
        id=get_demo_uuid("req_transit"), village_id=get_demo_uuid("vill_mod"), requester_id=get_demo_uuid("user_rep"),
        commodity_category="Medical/Blood/O2", commodity="DEMO Medical Kits", quantity=20, urgency="emergency", stockout_days=1,
        priority_score=92.0, status="assigned", fulfilled_quantity=0, created_at=now - timedelta(hours=4)
    )
    db.add_all([req_critical, req_high, req_normal, req_transit])
    db.commit()
    
    # Audit Logs for Requests
    for r in [req_critical, req_high, req_normal, req_transit]:
        db.add(models.EventLog(
            event_id=get_demo_uuid(f"evt_req_{r.id}"), event_type="SupplyRequestCreated",
            actor_id=get_demo_uuid("user_rep"), correlation_id=r.id,
            payload={"commodity": r.commodity, "quantity": r.quantity}, occurred_at=r.created_at
        ))
    db.commit()

    # --- 5. INCIDENT SCENARIO ---
    incident = models.Incident(
        id=get_demo_uuid("inc_1"), road_segment_id=get_demo_uuid("road_mod_diff"), reporter_id=get_demo_uuid("user_field"),
        incident_type="landslide", severity="medium", description="DEMO Partial Landslide", 
        geom=WKTElement(f'POINT({coords["MOD"][0]} {coords["MOD"][1]})', srid=4326), status="verified", confidence_score=0.9, created_at=now - timedelta(minutes=30)
    )
    db.add(incident)
    # Update road state
    db.query(models.RoadSegment).filter_by(id=get_demo_uuid("road_mod_diff")).update({"accessibility_state": "restricted"})
    db.commit()

    db.add(models.EventLog(
        event_id=get_demo_uuid("evt_inc_1"), event_type="IncidentReported",
        actor_id=get_demo_uuid("user_field"), correlation_id=get_demo_uuid("road_mod_diff"),
        payload={"incident_type": "landslide", "status": "verified"}, occurred_at=incident.created_at
    ))
    db.commit()

    # --- 6. DELIVERY & TELEMETRY ---
    delivery = models.Delivery(
        id=get_demo_uuid("del_1"), supply_request_id=get_demo_uuid("req_transit"), driver_id=get_demo_uuid("user_d1"),
        status="dispatched", dispatched_quantity=20, deviation_status="normal", created_at=now - timedelta(minutes=45),
        route_plan={"recommendation": {"route": {"total_cost": 35.0, "edge_details": [{"edge_id": str(get_demo_uuid("road_hq_near"))}, {"edge_id": str(get_demo_uuid("road_near_mod"))}]}}}
    )
    db.add(delivery)
    db.commit()

    db.add(models.EventLog(
        event_id=get_demo_uuid("evt_del_1"), event_type="DispatchApproved",
        actor_id=get_demo_uuid("user_control"), correlation_id=delivery.id,
        payload={"driver_id": str(get_demo_uuid("user_d1"))}, occurred_at=delivery.created_at
    ))
    db.commit()

    # Add Telemetry checkpoints
    t1 = models.DeliveryTelemetry(
        id=get_demo_uuid("tel_1"), delivery_id=delivery.id, source_type="mobile_gps",
        latitude=coords["HQ"][1], longitude=coords["HQ"][0], geom=WKTElement(f'POINT({coords["HQ"][0]} {coords["HQ"][1]})', srid=4326),
        speed_kmh=25.0, battery_level=90, captured_at=now - timedelta(minutes=40)
    )
    t2 = models.DeliveryTelemetry(
        id=get_demo_uuid("tel_2"), delivery_id=delivery.id, source_type="mobile_gps",
        latitude=coords["NEAR"][1], longitude=coords["NEAR"][0], geom=WKTElement(f'POINT({coords["NEAR"][0]} {coords["NEAR"][1]})', srid=4326),
        speed_kmh=45.0, battery_level=88, captured_at=now - timedelta(minutes=20)
    )
    # Current position slightly past NEAR
    curr_lat, curr_lng = 25.5300, 91.8570
    t3 = models.DeliveryTelemetry(
        id=get_demo_uuid("tel_3"), delivery_id=delivery.id, source_type="mobile_gps",
        latitude=curr_lat, longitude=curr_lng, geom=WKTElement(f'POINT({curr_lng} {curr_lat})', srid=4326),
        speed_kmh=40.0, battery_level=85, captured_at=now - timedelta(minutes=2)
    )
    db.add_all([t1, t2, t3])
    
    delivery.last_known_lat = curr_lat
    delivery.last_known_lng = curr_lng
    delivery.last_ping_at = t3.captured_at
    db.commit()

    # --- 7. ALERTS ---
    alert = models.Alert(
        id=get_demo_uuid("alt_1"), type="ElevatedRisk", severity="high",
        title="DEMO: Critical Medicine Request Risk", message="Weather forecast indicates Route B to DEMO-VILLAGE-REMOTE might be compromised.",
        related_request_id=get_demo_uuid("req_crit"), status="active", created_at=now - timedelta(minutes=15)
    )
    db.add(alert)
    db.commit()

    db.add(models.EventLog(
        event_id=get_demo_uuid("evt_alt_1"), event_type="AlertCreated",
        actor_id=get_demo_uuid("user_control"), correlation_id=get_demo_uuid("req_crit"),
        payload={"alert_type": alert.type, "severity": alert.severity}, occurred_at=alert.created_at
    ))
    db.commit()

    print("Successfully seeded all reliable demo datasets.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NER Sahayak Demo Seeder")
    parser.add_argument("--reset", action="store_true", help="Clear all demo data before seeding")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.reset:
            reset_demo_data(db)
        seed_demo_data(db)
    except Exception as e:
        print(f"Error seeding data: {e}")
        db.rollback()
    finally:
        db.close()
