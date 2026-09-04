import math
from sqlalchemy.orm import Session
from . import models

def sigmoid(x):
    return 1 / (1 + math.exp(-x))

def update_disruption_predictions(db: Session):
    roads = db.query(models.RoadSegment).all()
    
    for r in roads:
        latest_feature = db.query(models.SegmentFeature).filter(
            models.SegmentFeature.road_segment_id == r.id
        ).order_by(models.SegmentFeature.captured_at.desc()).first()
        
        if not latest_feature:
            continue
            
        f = latest_feature.features_json
        
        # P(Disruption) = sigmoid(B0 + B1*R_current + B2*R_24h + B3*R_72h + B4*S_slope + B5*H_hist + B6*C_cond)
        # Mock coefficients
        score = -4.0
        score += 0.05 * f.get("R_current", 0)
        score += 0.01 * f.get("R_24h", 0)
        score += 0.005 * f.get("R_72h", 0)
        
        slope_weights = {'flat': 0.0, 'moderate': 0.5, 'steep': 1.5}
        score += slope_weights.get(f.get("S_slope", "flat"), 0)
        
        score += 0.3 * f.get("H_hist", 0)
        
        cond_weights = {'good': 0.0, 'fair': 0.4, 'poor': 1.0}
        score += cond_weights.get(f.get("C_cond", "good"), 0)
        
        p = sigmoid(score)
        
        risk_band = "Low"
        if p >= 0.80:
            risk_band = "Severe"
        elif p >= 0.55:
            risk_band = "High"
        elif p >= 0.25:
            risk_band = "Moderate"
            
        factors = []
        if f.get("R_72h", 0) > 100: factors.append(f"72h Rainfall Accumulation ({f.get('R_72h')}mm)")
        if f.get("S_slope") == 'steep': factors.append("Steep Mountain Slope")
        if f.get("H_hist", 0) >= 3: factors.append("Frequent Historical Incidents")
        if f.get("C_cond") == 'poor': factors.append("Poor Road Structural Condition")
        
        if not factors:
            factors.append("Nominal conditions")
            
        r.disruption_probability = p
        r.predicted_risk_band = risk_band
        r.risk_factors = factors
        
    db.commit()
