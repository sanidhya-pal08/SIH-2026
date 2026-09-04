from sqlalchemy.orm import Session
from . import models

def sync_environmental_data(db: Session):
    roads = db.query(models.RoadSegment).all()
    # Mocking environmental ingestion (e.g., from Open-Meteo)
    for r in roads:
        # Generate deterministic mock features based on road ID
        seed = int(str(r.id)[0:4], 16)
        
        r_current = (seed % 10) * 2.5 # 0-22.5 mm/h
        r_24h = r_current * 12 + (seed % 20)
        r_72h = r_24h * 2 + (seed % 50)
        
        slopes = ['flat', 'moderate', 'steep']
        slope = slopes[seed % 3]
        
        h_hist = seed % 5
        
        conditions = ['good', 'fair', 'poor']
        c_cond = conditions[seed % 3]
        
        features = {
            "R_current": round(r_current, 2),
            "R_24h": round(r_24h, 2),
            "R_72h": round(r_72h, 2),
            "S_slope": slope,
            "H_hist": h_hist,
            "C_cond": c_cond
        }
        
        feat_record = models.SegmentFeature(
            road_segment_id=r.id,
            features_json=features
        )
        db.add(feat_record)
        
    db.commit()
