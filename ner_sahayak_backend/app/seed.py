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

    # Define Node Coordinates mapping (Longitude, Latitude) for East Khasi Hills
    coords = {
        "Shillong_HQ": (91.8933, 25.5788),
        "Upper_Shillong": (91.8600, 25.5450),
        "Mylliem": (91.8540, 25.5140),
        "Mawphlang": (91.7580, 25.4450),
        "Weiloi": (91.6850, 25.3520),
        "Mawsynram": (91.5820, 25.2970),
        "Cherrapunji": (91.7166, 25.2815),
        "Laitlyngkot": (91.8340, 25.4370),
        "Smit": (91.9280, 25.5310),
        "Pynursla": (91.8940, 25.3050),
        "Pongtung": (91.9500, 25.2500),
        "Dawki": (92.0150, 25.1850),
    }

    # Generate deterministic UUIDs for our mock nodes
    ids = {name: uuid.uuid5(uuid.NAMESPACE_DNS, name) for name in coords}

    villages = [
        models.Village(id=ids["Shillong_HQ"], name="Shillong HQ", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["Shillong_HQ"][0]} {coords["Shillong_HQ"][1]})', srid=4326), population=143229),
        models.Village(id=ids["Upper_Shillong"], name="Upper Shillong Depot", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["Upper_Shillong"][0]} {coords["Upper_Shillong"][1]})', srid=4326), population=5000),
        models.Village(id=ids["Mylliem"], name="Mylliem", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["Mylliem"][0]} {coords["Mylliem"][1]})', srid=4326), population=3200),
        models.Village(id=ids["Mawphlang"], name="Mawphlang", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["Mawphlang"][0]} {coords["Mawphlang"][1]})', srid=4326), population=4500),
        models.Village(id=ids["Weiloi"], name="Weiloi Junction", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["Weiloi"][0]} {coords["Weiloi"][1]})', srid=4326), population=1200),
        models.Village(id=ids["Mawsynram"], name="Mawsynram", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["Mawsynram"][0]} {coords["Mawsynram"][1]})', srid=4326), population=6000),
        models.Village(id=ids["Cherrapunji"], name="Sohra (Cherrapunji)", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["Cherrapunji"][0]} {coords["Cherrapunji"][1]})', srid=4326), population=14816),
        models.Village(id=ids["Laitlyngkot"], name="Laitlyngkot", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["Laitlyngkot"][0]} {coords["Laitlyngkot"][1]})', srid=4326), population=2500),
        models.Village(id=ids["Smit"], name="Smit", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["Smit"][0]} {coords["Smit"][1]})', srid=4326), population=7300),
        models.Village(id=ids["Pynursla"], name="Pynursla", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["Pynursla"][0]} {coords["Pynursla"][1]})', srid=4326), population=8500),
        models.Village(id=ids["Pongtung"], name="Pongtung", district="East Khasi Hills", geom=WKTElement(f'POINT({coords["Pongtung"][0]} {coords["Pongtung"][1]})', srid=4326), population=1100),
        models.Village(id=ids["Dawki"], name="Dawki Border Post", district="West Jaintia Hills", geom=WKTElement(f'POINT({coords["Dawki"][0]} {coords["Dawki"][1]})', srid=4326), population=3500),
    ]

    # Helper to generate LineString
    def make_line(u, v):
        return WKTElement(f'LINESTRING({coords[u][0]} {coords[u][1]}, {coords[v][0]} {coords[v][1]})', srid=4326)

    def create_road(source, target, name, d, t, risk=0.1, bridge=False, weight=None):
        return models.RoadSegment(
            name=name, source_id=ids[source], target_id=ids[target], geom=make_line(source, target),
            distance_km=d, base_travel_time_min=t, risk_level=risk, failure_probability=risk/2, resource_cost=d*2,
            road_type="primary", is_bridge=bridge, max_vehicle_weight_kg=weight, allows_hazmat=True
        )

    edges = [
        create_road("Shillong_HQ", "Upper_Shillong", "NH-06 Shillong City", 8.0, 20.0),
        create_road("Upper_Shillong", "Mylliem", "NH-06 Mylliem Approach", 7.5, 15.0),
        create_road("Mylliem", "Mawphlang", "SH-5 Mawphlang Road", 14.0, 30.0, 0.2),
        create_road("Mawphlang", "Weiloi", "SH-5 Weiloi Link", 15.0, 35.0, 0.25),
        create_road("Weiloi", "Mawsynram", "Mawsynram Route", 18.0, 45.0, 0.35),
        create_road("Weiloi", "Cherrapunji", "Sohra Road", 20.0, 50.0, 0.3),
        create_road("Mylliem", "Laitlyngkot", "NH-06 Laitlyngkot", 13.0, 25.0),
        create_road("Laitlyngkot", "Pynursla", "NH-06 Pynursla Pass", 19.0, 40.0, 0.4), # High risk landslide pass
        create_road("Pynursla", "Pongtung", "NH-06 Pongtung Link", 12.0, 25.0, 0.15),
        create_road("Pongtung", "Dawki", "Dawki Highway", 14.0, 30.0, 0.2),
        create_road("Shillong_HQ", "Smit", "Smit Connector", 16.0, 35.0),
        create_road("Smit", "Laitlyngkot", "Smit-Laitlyngkot Secondary", 15.0, 40.0, 0.25),
        create_road("Mawphlang", "Cherrapunji", "Cherrapunji Detour", 25.0, 65.0, 0.5), # Very steep/risky
        create_road("Upper_Shillong", "Laitlyngkot", "Upper Shillong Bypass", 18.0, 35.0, 0.1),
        create_road("Laitlyngkot", "Cherrapunji", "Sohra Shortcut", 24.0, 55.0, 0.3),
        # A river bridge near Dawki
        create_road("Pynursla", "Dawki", "Umngot River Bridge Route", 30.0, 60.0, 0.4, True, 10000.0) 
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
        name="Dr. Khongwir (Sohra Hospital)", role="village_rep", district="East Khasi Hills",
        email="hospital@nersahayak.gov.in", hashed_password=get_password_hash("hospital123")
    )
    db.add_all([admin, driver, village_rep])
    db.commit()

    # 3. Create a Golden Demo Supply Request
    urgent_request = models.SupplyRequest(
        village_id=ids["Cherrapunji"],
        requester_id=village_rep.id,
        commodity_category="Medical/Blood/O2",
        commodity="O2 Cylinders & Medical Kits",
        quantity=50,
        urgency="emergency",
        stockout_days=0,
        priority_score=95.5,
        priority_breakdown={
            "urgency_score": 60.0,
            "criticality_score": 30.0,
            "population_score": 8.34,
            "isolation_score": 0.0,
            "stockout_score": 20.0,
            "local_supply_penalty": 0.0,
            "raw_total": 118.34,
            "final_capped": 100.0
        },
        status="pending"
    )
    db.add(urgent_request)

    # 4. Create an Active Landslide Incident (Blocking the fastest route to Cherrapunji)
    bridge_edge = db.query(models.RoadSegment).filter(models.RoadSegment.name == "Sohra Road").first()
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
