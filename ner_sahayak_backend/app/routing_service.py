from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from . import models, graph_engine

def evaluate_routes(db: Session, source_id: str, target_id: str, vehicle_constraints: Any, policy_weights: Any) -> Dict[str, Any]:
    nodes = db.query(models.Village).all()
    edges = db.query(models.RoadSegment).all()
    
    if not nodes or not edges:
        return {
            "feasible": False,
            "summary": "Graph not seeded in PostGIS yet.",
            "constraints_applied": [],
            "recommendation": None,
            "alternatives": []
        }
        
    # Get all node coordinates
    villages = db.query(models.Village, func.ST_Y(models.Village.geom).label('lat'), func.ST_X(models.Village.geom).label('lng')).all()
    coords_map = {str(v.id): [lat, lng] for v, lat, lng in villages}

    graph = graph_engine.build_graph(nodes, edges)
    
    w_kg = vehicle_constraints.weight_kg if vehicle_constraints else None
    h_m = vehicle_constraints.height_m if vehicle_constraints else None
    hazmat = vehicle_constraints.is_hazmat if vehicle_constraints else False
    
    pruned_graph, pruned_log = graph_engine.prune_graph(
        graph, 
        vehicle_weight_kg=w_kg,
        vehicle_height_m=h_m,
        is_hazmat=hazmat
    )
    
    w_delay = policy_weights.delay if policy_weights else 1.0
    w_risk = policy_weights.risk if policy_weights else 1.0
    w_failure = policy_weights.failure if policy_weights else 1.0
    w_resource = policy_weights.resource if policy_weights else 1.0
    
    weighted_graph = graph_engine.apply_policy_weights(
        pruned_graph,
        w_delay=w_delay,
        w_risk=w_risk,
        w_failure=w_failure,
        w_resource=w_resource
    )
    
    paths = graph_engine.find_k_shortest_paths(weighted_graph, source_id, target_id, k=3)
    
    # Inject coordinates into paths so frontend can draw them easily
    for p in paths:
        path_coords = []
        for n in p["nodes"]:
            if n in coords_map:
                path_coords.append(coords_map[n])
        p["coordinates"] = path_coords

    confidence = graph_engine.compute_confidence(paths)
    rationale = graph_engine.build_rationale(paths, pruned_log, confidence)
    
    if not paths:
        rationale["feasible"] = False
        rationale["summary"] = "No safe road route available. Escalate to Air Delivery or Reachable Hub Handoff."
        # EPIC-09 Alert generation for critical requests
        from . import alert_service
        # Find nearest handoff
        handoff = alert_service.get_nearest_handoff(db)
        if handoff:
            rationale["summary"] += f" Nearest approved handoff: {handoff.name}."
            rationale["handoff_village_id"] = str(handoff.id)
            rationale["handoff_village_name"] = handoff.name
    else:
        rationale["feasible"] = True
        
    return rationale
