"""
graph_engine.py — Deterministic graph processing pipeline.

Three-stage pipeline:
  1. Hard constraint pruning   (prune_graph)
  2. Dynamic policy weighting  (apply_policy_weights)
  3. Yen's K-Shortest Paths    (find_k_shortest_paths)

Plus an explainability builder (build_rationale).

No ML. No heuristics. Every decision is auditable.
"""

from __future__ import annotations

import networkx as nx

from database import EdgeRow, NodeRow


# ───────────────────────────────────────────────────────────────────────
# 1. Graph construction
# ───────────────────────────────────────────────────────────────────────

def build_graph(nodes: list[NodeRow], edges: list[EdgeRow]) -> nx.DiGraph:
    """
    Construct a weighted directed graph from database rows.
    Edge attributes mirror the BCNF columns so downstream stages can
    reference them without a DB round-trip.
    """
    G = nx.DiGraph()

    for n in nodes:
        G.add_node(n.node_id, name=n.name, lat=n.latitude, lng=n.longitude)

    for e in edges:
        G.add_edge(
            e.source_node_id,
            e.target_node_id,
            edge_id=e.edge_id,
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
        )

    return G


# ───────────────────────────────────────────────────────────────────────
# 2. Hard constraint pruning
# ───────────────────────────────────────────────────────────────────────

def prune_graph(
    graph: nx.DiGraph,
    closed_edge_ids: set[str],
    unavailable_bridges: set[str],
    vehicle_weight_kg: float | None = None,
    vehicle_height_m: float | None = None,
    is_hazmat: bool = False,
) -> tuple[nx.DiGraph, list[dict]]:
    """
    Remove edges that violate hard constraints.

    Returns:
        pruned_graph: A copy of the graph with violating edges removed.
        pruned_log:   List of dicts documenting each removal (for explainability).
    """
    pruned = graph.copy()
    pruned_log: list[dict] = []

    edges_to_remove: list[tuple[str, str, str]] = []  # (u, v, reason)

    for u, v, data in pruned.edges(data=True):
        edge_id = data.get("edge_id", f"{u}->{v}")

        # Active road closure
        if edge_id in closed_edge_ids:
            edges_to_remove.append((u, v, f"Edge {edge_id} is actively closed"))
            continue

        # Unavailable / damaged bridge
        if data.get("is_bridge") and edge_id in unavailable_bridges:
            edges_to_remove.append(
                (u, v, f"Bridge {edge_id} is unavailable / damaged")
            )
            continue

        # Vehicle weight restriction
        max_weight = data.get("max_vehicle_weight_kg")
        if vehicle_weight_kg is not None and max_weight is not None:
            if vehicle_weight_kg > max_weight:
                edges_to_remove.append(
                    (u, v, f"Vehicle weight {vehicle_weight_kg}kg exceeds "
                           f"edge {edge_id} limit {max_weight}kg")
                )
                continue

        # Vehicle height restriction
        max_height = data.get("max_vehicle_height_m")
        if vehicle_height_m is not None and max_height is not None:
            if vehicle_height_m > max_height:
                edges_to_remove.append(
                    (u, v, f"Vehicle height {vehicle_height_m}m exceeds "
                           f"edge {edge_id} limit {max_height}m")
                )
                continue

        # Hazmat restriction
        if is_hazmat and not data.get("allows_hazmat", True):
            edges_to_remove.append(
                (u, v, f"Edge {edge_id} does not allow hazmat transport")
            )
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
    """
    Compute composite edge cost using the exact policy formula:

        Edge Cost = Travel Delay Cost
                  + Route Risk Cost
                  + Failure Cost
                  + Resource Cost

    Each sub-cost = raw_attribute × policy_weight.

    The breakdown is stored on each edge for downstream explainability.
    The composite cost is written to ``data["weight"]`` so NetworkX
    pathfinding functions use it automatically.
    """
    for _u, _v, data in graph.edges(data=True):
        delay_cost = data.get("base_travel_time_min", 0.0) * w_delay
        risk_cost = data.get("risk_level", 0.0) * w_risk
        failure_cost = data.get("failure_probability", 0.0) * w_failure
        resource_cost = data.get("resource_cost", 0.0) * w_resource

        total = delay_cost + risk_cost + failure_cost + resource_cost

        # Store breakdown for explainability
        data["cost_breakdown"] = {
            "travel_delay_cost": round(delay_cost, 6),
            "route_risk_cost": round(risk_cost, 6),
            "failure_cost": round(failure_cost, 6),
            "resource_cost": round(resource_cost, 6),
            "total": round(total, 6),
        }
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
) -> list[dict]:
    """
    Use ``networkx.shortest_simple_paths`` (Yen's algorithm) to find
    the *k* lowest-cost simple paths from *source* to *target*.

    Returns a list of path dicts, each containing:
      - nodes:          ordered list of node IDs
      - total_cost:     sum of edge weights along the path
      - edge_details:   per-edge cost breakdowns
      - rank:           1-indexed position
    """
    paths: list[dict] = []

    try:
        gen = nx.shortest_simple_paths(graph, source, target, weight="weight")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return paths

    for i, node_list in enumerate(gen):
        if i >= k:
            break

        total_cost = 0.0
        edge_details: list[dict] = []

        for a, b in zip(node_list, node_list[1:]):
            edata = graph.edges[a, b]
            cost_bd = edata.get("cost_breakdown", {})
            total_cost += edata.get("weight", 0.0)
            edge_details.append({
                "edge_id": edata.get("edge_id", f"{a}->{b}"),
                "from": a,
                "to": b,
                "cost_breakdown": cost_bd,
            })

        paths.append({
            "rank": i + 1,
            "nodes": node_list,
            "total_cost": round(total_cost, 6),
            "edge_details": edge_details,
        })

    return paths


def compute_confidence(paths: list[dict]) -> float:
    """
    Confidence score based on cost separation between best and second-best.

        confidence = 1 − (best_cost / second_best_cost)

    Returns 1.0 if only one path exists (no alternative).
    Returns 0.0 if no paths exist.
    """
    if len(paths) == 0:
        return 0.0
    if len(paths) == 1:
        return 1.0

    best = paths[0]["total_cost"]
    second = paths[1]["total_cost"]

    if second == 0:
        return 0.0

    return round(1.0 - (best / second), 6)


# ───────────────────────────────────────────────────────────────────────
# 5. Explainability
# ───────────────────────────────────────────────────────────────────────

def build_rationale(
    paths: list[dict],
    pruned_log: list[dict],
    confidence: float,
) -> dict:
    """
    Build a human-readable rationale for the routing decision.
    """
    if not paths:
        return {
            "summary": "No feasible route found after constraint pruning.",
            "constraints_applied": pruned_log,
            "recommendation": None,
        }

    best = paths[0]
    alternatives = paths[1:]

    summary_parts = [
        f"Recommended route (rank 1) traverses {len(best['nodes'])} nodes "
        f"with a total weighted cost of {best['total_cost']:.4f}.",
    ]

    if pruned_log:
        summary_parts.append(
            f"{len(pruned_log)} edge(s) were removed due to hard constraints."
        )

    if alternatives:
        summary_parts.append(
            f"{len(alternatives)} alternative route(s) available. "
            f"Confidence in top recommendation: {confidence:.2%}."
        )
    else:
        summary_parts.append(
            "No alternative routes available — this is the only feasible path."
        )

    return {
        "summary": " ".join(summary_parts),
        "constraints_applied": pruned_log,
        "recommendation": {
            "route": best,
            "confidence": confidence,
            "reason": (
                "Selected as lowest composite cost after hard-constraint pruning "
                "and policy-weighted scoring. Every sub-cost (delay, risk, failure, "
                "resource) is broken down per edge for auditability."
            ),
        },
        "alternatives": alternatives,
    }
