-- Enable PostGIS extension for geospatial features
CREATE EXTENSION IF NOT EXISTS postgis;

-- ==========================================
-- 1. IDENTITY & RBAC
-- ==========================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL, -- 'control_room', 'field_officer', 'driver', 'admin'
    district VARCHAR(100),
    phone_number VARCHAR(20) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ==========================================
-- 2. GIS & NETWORK (Roads & Locations)
-- ==========================================
CREATE TABLE road_segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255),
    geom geometry(LineString, 4326), -- Geospatial LineString for the road
    accessibility_state VARCHAR(50) DEFAULT 'open', -- 'open', 'restricted', 'hazardous', 'blocked'
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE villages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    district VARCHAR(100) NOT NULL,
    geom geometry(Point, 4326), -- Geospatial Point for village location
    population INT,
    isolation_score FLOAT DEFAULT 0.0
);

-- ==========================================
-- 3. INCIDENTS & FIELD REPORTS
-- ==========================================
CREATE TABLE incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    road_segment_id UUID REFERENCES road_segments(id),
    reporter_id UUID REFERENCES users(id),
    incident_type VARCHAR(50), -- 'landslide', 'flood', 'bridge_failure'
    geom geometry(Point, 4326),
    evidence_url TEXT, -- URL to photo in object storage
    confidence_score FLOAT DEFAULT 1.0,
    status VARCHAR(50) DEFAULT 'pending_review', -- 'pending_review', 'verified', 'rejected'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ==========================================
-- 4. SUPPLY REQUESTS & DELIVERIES
-- ==========================================
CREATE TABLE supply_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    village_id UUID REFERENCES villages(id),
    requester_id UUID REFERENCES users(id),
    commodity VARCHAR(100) NOT NULL,
    quantity INT NOT NULL,
    urgency VARCHAR(50) DEFAULT 'routine', -- 'routine', 'urgent', 'emergency'
    priority_score FLOAT DEFAULT 0.0,
    status VARCHAR(50) DEFAULT 'open', -- 'open', 'assigned', 'delivered'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supply_request_id UUID REFERENCES supply_requests(id),
    driver_id UUID REFERENCES users(id),
    route_plan JSONB, -- Stores the GeoJSON/array of the approved route
    status VARCHAR(50) DEFAULT 'dispatched', -- 'dispatched', 'rerouted', 'delivered', 'failed'
    pod_notes TEXT, -- Proof of delivery notes
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    delivered_at TIMESTAMP WITH TIME ZONE
);

-- ==========================================
-- 5. IMMUTABLE EVENT LEDGER (Audit Trail)
-- ==========================================
CREATE TABLE event_log (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL, -- e.g., 'RoadAccessibilityChanged', 'DispatchApproved'
    actor_id UUID, -- Who did it
    correlation_id UUID, -- ID of the incident/delivery this relates to
    payload JSONB NOT NULL, -- The full state change
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    received_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_road_segments_geom ON road_segments USING GIST (geom);
CREATE INDEX idx_villages_geom ON villages USING GIST (geom);
CREATE INDEX idx_incidents_geom ON incidents USING GIST (geom);
CREATE INDEX idx_event_log_type ON event_log(event_type);
