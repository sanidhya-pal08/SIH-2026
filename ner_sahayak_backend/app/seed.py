import uuid
from sqlalchemy.orm import Session
from geoalchemy2.elements import WKTElement

from . import models

def seed_demo_graph(db: Session) -> None:
    """
    Seed a small demo graph for the SIH Hackathon (East Khasi Hills / Base Camp mock).
    Only inserts if the villages table is empty.
    """
    if db.query(models.Village).first() is not None:
        return

    # Define Node Coordinates mapping for Edge creation
    coords = {
        "N1": (77.2090, 28.6139),
        "N2": (77.2150, 28.6200),
        "N3": (77.2050, 28.6280),
        "N4": (77.2200, 28.6350),
        "N5": (77.2300, 28.6100),
        "N6": (77.2100, 28.6400),
    }

    # Generate deterministic UUIDs for our mock nodes so edges can reference them
    n1_id = uuid.uuid5(uuid.NAMESPACE_DNS, "N1")
    n2_id = uuid.uuid5(uuid.NAMESPACE_DNS, "N2")
    n3_id = uuid.uuid5(uuid.NAMESPACE_DNS, "N3")
    n4_id = uuid.uuid5(uuid.NAMESPACE_DNS, "N4")
    n5_id = uuid.uuid5(uuid.NAMESPACE_DNS, "N5")
    n6_id = uuid.uuid5(uuid.NAMESPACE_DNS, "N6")

    id_map = {
        "N1": n1_id, "N2": n2_id, "N3": n3_id, 
        "N4": n4_id, "N5": n5_id, "N6": n6_id
    }

    villages = [
        models.Village(id=n1_id, name="Base Camp Alpha", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["N1"][0]} {coords["N1"][1]})', srid=4326)),
        models.Village(id=n2_id, name="Field Hospital", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["N2"][0]} {coords["N2"][1]})', srid=4326)),
        models.Village(id=n3_id, name="Supply Depot", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["N3"][0]} {coords["N3"][1]})', srid=4326)),
        models.Village(id=n4_id, name="Evacuation Point", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["N4"][0]} {coords["N4"][1]})', srid=4326)),
        models.Village(id=n5_id, name="Shelter Zone", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["N5"][0]} {coords["N5"][1]})', srid=4326)),
        models.Village(id=n6_id, name="Command Center", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["N6"][0]} {coords["N6"][1]})', srid=4326)),
    ]

    # Helper to generate LineString
    def make_line(u, v):
        return WKTElement(f'LINESTRING({coords[u][0]} {coords[u][1]}, {coords[v][0]} {coords[v][1]})', srid=4326)

    edges = [
        # N1 -> N2
        models.RoadSegment(name="Route Alpha-Med", source_id=n1_id, target_id=n2_id, geom=make_line("N1", "N2"), distance_km=1.2, base_travel_time_min=4.0, risk_level=0.1, failure_probability=0.05, resource_cost=10.0, road_type="primary", is_bridge=False, allows_hazmat=True),
        # N1 -> N3
        models.RoadSegment(name="Depot Supply Line", source_id=n1_id, target_id=n3_id, geom=make_line("N1", "N3"), distance_km=2.5, base_travel_time_min=8.0, risk_level=0.05, failure_probability=0.02, resource_cost=15.0, road_type="primary", is_bridge=False, allows_hazmat=True),
        # N2 -> N4 (Bridge)
        models.RoadSegment(name="Hospital Evac Bridge", source_id=n2_id, target_id=n4_id, geom=make_line("N2", "N4"), distance_km=2.0, base_travel_time_min=6.0, risk_level=0.3, failure_probability=0.15, resource_cost=20.0, road_type="secondary", is_bridge=True, max_vehicle_weight_kg=10000.0, allows_hazmat=False),
        # N3 -> N4
        models.RoadSegment(name="Depot Evac Route", source_id=n3_id, target_id=n4_id, geom=make_line("N3", "N4"), distance_km=3.0, base_travel_time_min=10.0, risk_level=0.15, failure_probability=0.08, resource_cost=25.0, road_type="primary", is_bridge=False, allows_hazmat=True),
        # N2 -> N5
        models.RoadSegment(name="Shelter Connector", source_id=n2_id, target_id=n5_id, geom=make_line("N2", "N5"), distance_km=1.8, base_travel_time_min=5.0, risk_level=0.2, failure_probability=0.10, resource_cost=12.0, road_type="secondary", is_bridge=False, allows_hazmat=True),
        # N5 -> N4
        models.RoadSegment(name="Shelter Evac Route", source_id=n5_id, target_id=n4_id, geom=make_line("N5", "N4"), distance_km=3.5, base_travel_time_min=12.0, risk_level=0.25, failure_probability=0.12, resource_cost=30.0, road_type="tertiary", is_bridge=False, max_vehicle_weight_kg=5000.0, allows_hazmat=True),
        # N3 -> N6
        models.RoadSegment(name="Command Supply Route", source_id=n3_id, target_id=n6_id, geom=make_line("N3", "N6"), distance_km=2.2, base_travel_time_min=7.0, risk_level=0.10, failure_probability=0.03, resource_cost=18.0, road_type="primary", is_bridge=False, allows_hazmat=True),
        # N6 -> N4 (Bridge)
        models.RoadSegment(name="Command Evac Bridge", source_id=n6_id, target_id=n4_id, geom=make_line("N6", "N4"), distance_km=1.5, base_travel_time_min=5.0, risk_level=0.20, failure_probability=0.07, resource_cost=22.0, road_type="secondary", is_bridge=True, max_vehicle_weight_kg=15000.0, allows_hazmat=True),
    ]

    # 1. Create Villages & Edges (Nodes & Links)
    db.add_all(villages)
    db.commit() # Commit villages first to satisfy Foreign Key constraints
    
    db.add_all(edges)
    db.commit() # Commit edges next
    
    # 2. Create Users for the Demo
    from .auth import get_password_hash
    
    admin = models.User(
        name="Control Room Admin", role="control_room", district="East Khasi Hills",
        email="admin@nersahayak.gov.in", hashed_password=get_password_hash("admin123")
    )
    driver = models.User(
        name="John (Driver)", role="driver", district="East Khasi Hills",
        email="driver@nersahayak.gov.in", hashed_password=get_password_hash("driver123")
    )
    village_rep = models.User(
        name="Dr. Smith (Hospital)", role="village_rep", district="East Khasi Hills",
        email="hospital@nersahayak.gov.in", hashed_password=get_password_hash("hospital123")
    )
    db.add_all([admin, driver, village_rep])
    db.commit()

    # 3. Create a Golden Demo Supply Request
    urgent_request = models.SupplyRequest(
        village_id=n4_id,
        requester_id=village_rep.id,
        commodity="O2 Cylinders & Medical Kits",
        quantity=50,
        urgency="emergency",
        priority_score=95.5,
        status="pending"
    )
    db.add(urgent_request)

    # 4. Create an Active Landslide Incident (Blocking the fastest route!)
    # We will block the "Hospital Evac Bridge" (N2 -> N4) so the AI is forced to reroute.
    bridge_edge = db.query(models.RoadSegment).filter(models.RoadSegment.name == "Hospital Evac Bridge").first()
    if bridge_edge:
        bridge_edge.accessibility_state = "blocked"
        
        landslide = models.Incident(
            road_segment_id=bridge_edge.id,
            reporter_id=admin.id,
            incident_type="landslide",
            confidence_score=99.0,
            status="verified"
        )
        db.add(landslide)

    db.commit()
    print("Successfully seeded the NER Sahayak Golden Demo data!")
