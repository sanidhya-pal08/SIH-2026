# 🗺️GIS Router - Engine

An intelligent, hazard-aware routing engine designed for emergency response and dynamic field conditions. Built for the Smart India Hackathon 2026, this backend service prioritizes **safety, explainability, and absolute accountability.**

Unlike standard routing APIs, this engine dynamically prunes road networks based on real-time disaster data (floods, bridge failures) and logs every single calculation into an immutable, BCNF-normalized database for post-event auditing.

## ✨ Core Architecture & Features

* **Dynamic Graph Pruning:** Utilizes `NetworkX` to instantly sever edges and recalculate paths when hard constraints (like a flooded road) are reported.
* **Yen's K-Shortest Paths:** Doesn't just find one route. It computes the top alternative paths, allowing field commanders to make informed choices.
* **Explainable Routing:** Every response includes a full cost breakdown (travel delay, risk, resource cost), a mathematically derived confidence score, and a plain-English rationale for why a route was chosen.
* **Immutable Audit Trail:** Powered by a heavily constrained SQLite database. Every incident payload and resulting route is permanently logged. A strict `UNIQUE` constraint on `event_id` prevents duplicate processing.

## 🚀 Quick Start (Docker)

The entire engine is containerized for zero-friction deployment.

1. **Clone the repository and spin up the container:**
   ```bash
   docker-compose up --build -d


Access the API Documentation:
Open your browser and navigate to http://localhost:8000/docs to view the interactive FastAPI Swagger UI.

📡 Example API Usage
The engine exposes a /route endpoint that accepts environmental hazard reports and calculates the safest path.

Request (POST /route):

JSON
{
  "source_node": "N1",
  "target_node": "N4",
  "urgency_profile": "emergency",
  "vehicle_weight_kg": 8000,
  "incident": {
    "event_id": "550e8400-e29b-41d4-a716-446655440003",
    "event_type": "RoadAccessibilityChanged",
    "occurred_at": "2026-08-30T10:00:00Z",
    "source": "officer-774",
    "closed_edge_ids": ["E3"]
  }
}
Key Response Highlights:

"constraints_applied": Explicitly lists edges removed from the graph (e.g., Edge E3 is actively closed).

"paths": Ranked array of routes with granular cost breakdowns per edge.

"confidence_score": The algorithmic confidence in the Rank 1 recommendation compared to alternatives.

🗄️ Database Auditing
To verify the immutability of the audit logs locally, you can query the database directly inside the Docker container:

Bash
docker exec sih2026gisrouter-gis-engine-1 python -c "import sqlite3; conn = sqlite3.connect('/app/data/router.db'); print(conn.execute('SELECT event_id, best_route_cost FROM route_audit;').fetchall())"