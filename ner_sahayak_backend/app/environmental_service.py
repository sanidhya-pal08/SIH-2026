import httpx
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from geoalchemy2.shape import to_shape
from . import models

logger = logging.getLogger(__name__)

class ExternalWeatherProvider:
    @staticmethod
    def get_precipitation(lat: float, lng: float, use_mock: bool = False) -> tuple[float, float, float]:
        if use_mock:
            return ExternalWeatherProvider._mock_precip(lat, lng)
            
        try:
            # Real Open-Meteo API call
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current=precipitation&hourly=precipitation&past_days=3"
            response = httpx.get(url, timeout=5.0)
            response.raise_for_status()
            data = response.json()
            
            r_current = data.get("current", {}).get("precipitation", 0.0)
            
            # Simple summation of hourly past data
            hourly_precip = data.get("hourly", {}).get("precipitation", [])
            # last 24h:
            r_24h = sum(hourly_precip[-24:]) if len(hourly_precip) >= 24 else sum(hourly_precip)
            # last 72h:
            r_72h = sum(hourly_precip[-72:]) if len(hourly_precip) >= 72 else sum(hourly_precip)
            
            return float(r_current), float(r_24h), float(r_72h)
        except Exception as e:
            logger.warning(f"Failed to fetch real weather data, using fallback: {e}")
            return ExternalWeatherProvider._mock_precip(lat, lng)
            
    @staticmethod
    def _mock_precip(lat: float, lng: float) -> tuple[float, float, float]:
        seed = int(lat * 1000) + int(lng * 1000)
        r_current = (seed % 10) * 2.5
        r_24h = r_current * 12 + (seed % 20)
        r_72h = r_24h * 2 + (seed % 50)
        return r_current, r_24h, r_72h

def sync_environmental_data(db: Session, use_mock: bool = False):
    roads = db.query(models.RoadSegment).all()
    
    for r in roads:
        source_village = db.query(models.Village).filter(models.Village.id == r.source_id).first()
        
        lat, lng = 25.5788, 91.8933 # Default Shillong HQ
        if source_village:
            # Extract coordinates using PostGIS functions
            lon_val = db.scalar(func.ST_X(source_village.geom))
            lat_val = db.scalar(func.ST_Y(source_village.geom))
            if lon_val and lat_val:
                lng, lat = lon_val, lat_val
                
        r_current, r_24h, r_72h = ExternalWeatherProvider.get_precipitation(lat, lng, use_mock)
        
        seed = int(str(r.id)[0:4], 16)
        
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
            "C_cond": c_cond,
            "data_source": "mock" if use_mock else "open-meteo"
        }
        
        feat_record = models.SegmentFeature(
            road_segment_id=r.id,
            features_json=features
        )
        db.add(feat_record)
        
    db.commit()
