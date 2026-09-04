import pytest
from sqlalchemy import func
from app.database import SessionLocal
from app import models

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    yield db
    db.close()

def test_postgis_geometries_valid(db_session):
    """Verify PostGIS geometry validity and SRID for all road segments and villages."""
    roads = db_session.query(
        models.RoadSegment.name,
        func.ST_IsValid(models.RoadSegment.geom).label("is_valid"),
        func.ST_SRID(models.RoadSegment.geom).label("srid"),
        func.ST_GeometryType(models.RoadSegment.geom).label("geom_type")
    ).all()
    assert len(roads) > 0, "Road segments must exist in DB"
    for r in roads:
        assert r.is_valid is True, f"Road {r.name} has invalid geometry"
        assert r.srid == 4326, f"Road {r.name} SRID is {r.srid}, expected 4326"
        assert "LINESTRING" in r.geom_type.upper(), f"Road {r.name} geometry type is {r.geom_type}"

    villages = db_session.query(
        models.Village.name,
        func.ST_IsValid(models.Village.geom).label("is_valid"),
        func.ST_SRID(models.Village.geom).label("srid"),
        func.ST_GeometryType(models.Village.geom).label("geom_type")
    ).all()
    assert len(villages) > 0, "Villages must exist in DB"
    for v in villages:
        assert v.is_valid is True, f"Village {v.name} has invalid geometry"
        assert v.srid == 4326, f"Village {v.name} SRID is {v.srid}, expected 4326"
        assert "POINT" in v.geom_type.upper(), f"Village {v.name} geometry type is {v.geom_type}"

def test_geographic_bounding_box(db_session):
    """Verify all seeded geometries fall within Northeast India (Meghalaya bounds)."""
    # Meghalaya rough bounds: Lat [25.0, 26.2], Lng [89.8, 92.9]
    village_coords = db_session.query(
        models.Village.name,
        func.ST_Y(models.Village.geom).label("lat"),
        func.ST_X(models.Village.geom).label("lng")
    ).all()
    for v in village_coords:
        assert 25.0 <= v.lat <= 26.2, f"Village {v.name} latitude {v.lat} outside expected bounds"
        assert 89.8 <= v.lng <= 92.9, f"Village {v.name} longitude {v.lng} outside expected bounds"
