from __future__ import annotations
import networkx as nx
from typing import List, Tuple, Dict, Set, Optional

from .models import Village, RoadSegment

# ───────────────────────────────────────────────────────────────────────
# 1. Graph construction
# ───────────────────────────────────────────────────────────────────────
def build_graph(nodes: List[Village], edges: List[RoadSegment]) -> nx.DiGraph:
    G = nx.DiGraph()

    for n in nodes:
        # Assuming lat/lng isn't directly accessed from WKB geom in this mock, 
        # normally you'd use geoalchemy to extract it. Using dummy for graph.
        G.add_node(str(n.id), name=n.name)

    for e in edges:
        # Only add edge if source and target are defined
        if e.source_id and e.target_id:
            G.add_edge(
                str(e.source_id),
                str(e.target_id),
                edge_id=str(e.id),
                distance_km=e.distance_km,
                base_travel_time_min=e.base_travel_time_min,
                risk_level=e.risk_level,
                failure_probability=e.failure_probability,
                resource_cost=e.resource_cost,
                road_type=e.road_type,
                is_bridge=e.is_bridge,
                max_vehicle_weight_kg=e.max_vehicle_weight_kg,
                max_vehicle_height_m=getattr(e, "max_vehicle_height_m", None),
                allows_hazmat=e.allows_hazmat,
                accessibility_state=e.accessibility_state,
                disruption_probability=e.disruption_probability,
            )

    return G

# ───────────────────────────────────────────────────────────────────────
# 2. Hard constraint pruning
# ───────────────────────────────────────────────────────────────────────
def prune_graph(
    graph: nx.DiGraph,
    vehicle_weight_kg: Optional[float] = None,
    vehicle_height_m: Optional[float] = None,
    is_hazmat: bool = False,
) -> Tuple[nx.DiGraph, List[Dict]]:
    pruned = graph.copy()
    pruned_log: List[Dict] = []
    edges_to_remove: List[Tuple[str, str, str]] = [] 

    for u, v, data in pruned.edges(data=True):
        edge_id = data.get("edge_id", f"{u}->{v}")

        # Active road closure from Database State
        if data.get("accessibility_state") in ["closed", "blocked"]:
            edges_to_remove.append((u, v, f"Edge {edge_id} is actively closed or blocked"))
            continue

        # Vehicle weight restriction
        max_weight = data.get("max_vehicle_weight_kg")
        if vehicle_weight_kg is not None and max_weight is not None:
            if vehicle_weight_kg > max_weight:
                edges_to_remove.append(
                    (u, v, f"Vehicle weight {vehicle_weight_kg}kg exceeds edge {edge_id} limit {max_weight}kg")
                )
                continue

        # Hazmat restriction
        if is_hazmat and not data.get("allows_hazmat", True):
            edges_to_remove.append((u, v, f"Edge {edge_id} does not allow hazmat transport"))
            continue

    for u, v, reason in edges_to_remove:
        pruned.remove_edge(u, v)
        pruned_log.append({"edge": f"{u}->{v}", "reason": reason})

    return pruned, pruned_log

# ───────────────────────────────────────────────────────────────────────
# 3. Dynamic policy weighting
# ───────────────────────────────────────────────────────────────────────
def apply_policy_weights(
    graph: nx.DiGraph,
    w_delay: float = 1.0,
    w_risk: float = 1.0,
    w_failure: float = 1.0,
    w_resource: float = 1.0,
) -> nx.DiGraph:
    for _u, _v, data in graph.edges(data=True):
        delay_cost = data.get("base_travel_time_min", 0.0) * w_delay
        
        # Inject Epic 4: P^2 penalty
        p_disruption = data.get("disruption_probability") or 0.0
        risk_cost = (data.get("risk_level", 0.0) + (p_disruption ** 2) * 60) * w_risk
        
        failure_cost = data.get("failure_probability", 0.0) * w_failure
        resource_cost = data.get("resource_cost", 0.0) * w_resource

        total = delay_cost + risk_cost + failure_cost + resource_cost
        data["cost_breakdown"] = {
            "travel_delay_cost": round(delay_cost, 6),
            "route_risk_cost": round(risk_cost, 6),
            "failure_cost": round(failure_cost, 6),
            "resource_cost": round(resource_cost, 6),
            "total": round(total, 6),
            "disruption_probability": round(p_disruption, 4)
        }
        data["weight"] = total
        data["weight"] = total

    return graph

# ───────────────────────────────────────────────────────────────────────
# 4. Yen's K-Shortest Paths
# ───────────────────────────────────────────────────────────────────────
def find_k_shortest_paths(
    graph: nx.DiGraph,
    source: str,
    target: str,
    k: int = 3,
) -> List[Dict]:
    paths: List[Dict] = []
    try:
        gen = nx.shortest_simple_paths(graph, source, target, weight="weight")
        for i, node_list in enumerate(gen):
            if i >= k:
                break

            total_cost = 0.0
            edge_details: List[Dict] = []
            for a, b in zip(node_list, node_list[1:]):
                edata = graph.edges[a, b]
                cost_bd = edata.get("cost_breakdown", {})
                total_cost += edata.get("weight", 0.0)
                edge_details.append({
                    "edge_id": edata.get("edge_id", f"{a}->{b}"),
                    "from_node": a,
                    "to_node": b,
                    "cost_breakdown": cost_bd,
                })

            paths.append({
                "rank": i + 1,
                "nodes": node_list,
                "total_cost": round(total_cost, 6),
                "edge_details": edge_details,
            })
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        pass

    return paths

def compute_confidence(paths: List[Dict]) -> float:
    if len(paths) == 0:
        return 0.0
    if len(paths) == 1:
        return 1.0

    best = paths[0]["total_cost"]
    second = paths[1]["total_cost"]

    if second == 0:
        return 0.0

    return round(1.0 - (best / second), 6)

def build_rationale(paths: List[Dict], pruned_log: List[Dict], confidence: float) -> dict:
    if not paths:
        return {
            "summary": "No feasible route found after constraint pruning.",
            "constraints_applied": pruned_log,
            "recommendation": None,
            "alternatives": []
        }

    best = paths[0]
    alternatives = paths[1:]
    
    # Epic 4: Check if any high risk in best route
    high_risk_edge = None
    for ed in best.get("edge_details", []):
        p = ed.get("cost_breakdown", {}).get("disruption_probability", 0.0)
        if p > 0.70:
            high_risk_edge = ed
            break
            
    if high_risk_edge:
        summary_parts = [
            f"Primary route traverses {len(best['nodes'])} nodes but contains HIGH RISK corridor (Edge {high_risk_edge['edge_id']}) "
            f"with disruption probability {high_risk_edge['cost_breakdown']['disruption_probability']:.1%}."
        ]
        
        # Inject wait window alternative
        wait_window_alt = {
            "rank": "Wait-Window",
            "nodes": best["nodes"],
            "total_cost": "N/A (Wait 6h for rainfall cessation)",
            "edge_details": best["edge_details"],
            "is_wait_window": True
        }
        
        # if we have alternatives, we can detour
        if alternatives:
            summary_parts.append(
                f"Diverting via Rank {alternatives[0]['rank']} increases travel cost to {alternatives[0]['total_cost']:.2f} but avoids the high-risk zone."
            )
        
        alternatives.insert(0, wait_window_alt)
        
    else:
        summary_parts = [f"Recommended route (rank 1) traverses {len(best['nodes'])} nodes with a cost of {best['total_cost']:.4f}."]
    
    if pruned_log:
        summary_parts.append(f"{len(pruned_log)} edge(s) were removed due to hard constraints.")
    if alternatives and not high_risk_edge:
        summary_parts.append(f"{len(alternatives)} alternative route(s) available. Confidence: {confidence:.2%}.")
    elif not alternatives:
        summary_parts.append("No alternative routes available.")

    return {
        "summary": " ".join(summary_parts),
        "constraints_applied": pruned_log,
        "recommendation": {
            "route": best,
            "confidence": confidence,
            "reason": "Selected as lowest composite cost after constraint pruning and policy-weighted scoring."
        },
        "alternatives": alternatives,
    }
