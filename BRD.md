# Business Requirements Document

## AI-Based Smart Logistics and Accessibility Intelligence Platform for NER

**Problem Statement:** ID26002  
**Sponsor:** Ministry of Development of North Eastern Region (MDoNER)  
**Theme:** Transportation & Logistics  
**Version:** 1.0  
**Date:** 2026-08-29  
**Status:** Draft for validation

## 1. Executive Summary

NER faces unreliable logistics caused by difficult terrain, landslides, floods, heavy rainfall, bridge failures, limited connectivity, and fragmented operational information. This platform, called **NER Sahayak** in this document, combines GIS, weather data, field reports, vehicle locations, and supply requests to help authorities decide what to deliver, where to deliver it first, and whether to dispatch, reroute, wait, consolidate, use local carriers, or escalate to air delivery.

The shortest route is not automatically the best route. Recommendations balance urgency, disaster probability, expected delay, vehicle constraints, route reliability, available resources, and the safety of the return journey. The MVP will demonstrate the complete operational loop for selected pilot districts: request, prioritize, plan, dispatch, monitor, report disruption, alert, reroute, and confirm delivery.

## 2. Business Problem

Current operations may not provide a shared, real-time view of road accessibility, affected communities, active deliveries, supply shortages, and changing weather. This can result in delayed medicines and food, avoidable unsafe trips, repeated village-to-village journeys, poor coordination among departments, and weak evidence for infrastructure planning.

## 3. Objectives

1. Provide a district and corridor-level operational picture of accessibility and logistics.
2. Identify and prioritize the most affected locations.
3. Recommend routes using risk, delay, distance, reliability, vehicle capability, and urgency.
4. Support dispatch, reroute, wait-for-safer-window, hub handoff, local carrier, and emergency escalation decisions.
5. Capture geo-tagged reports, photos, and delivery evidence from low-network areas.
6. Provide multilingual alerts, offline operation, auditability, and decision explanations.
7. Create historical evidence for infrastructure and resilience planning.

## 4. Stakeholders and Users

| Stakeholder | Needs |
|---|---|
| MDoNER / national coordination | Regional visibility and investment evidence |
| State and district control rooms | Prioritization, dispatch, alerts, escalation |
| Disaster-management authorities | Emergency routes and air-delivery coordination |
| Roads and transport departments | Verified asset status and repair priorities |
| Logistics operators and drivers | Safe route, instructions, and offline status |
| Field officials and local agents | Fast incident reporting with evidence |
| Village representatives | Requests, receiving coordination, and local handoff |
| Health, food, and public-service facilities | Stock requests and delivery confirmation |
| Administrators | Users, thresholds, sources, data quality, and audits |

## 5. Scope

### MVP in scope

- Web control-room dashboard with GIS map.
- Offline-first mobile field application.
- District, village, facility, road, bridge, hub, helipad, incident, vehicle, and delivery records.
- Accessibility states: open, restricted, hazardous, blocked, and unknown.
- Supply requests, inventory snapshots, prioritization, assignment, and proof of delivery.
- Weather and incident ingestion through configurable adapters.
- Route alternatives showing distance, ETA, delay, risk, confidence, and blocked segments.
- Urgent, emergency, routine, and wait-when-safe decision profiles.
- GPS tracking when a location feed is available.
- Alerts with acknowledgement and escalation.
- Multilingual templates, audit trail, role-based access, and operational reports.

### Future scope

Satellite/imagery damage detection, advanced historical ML, digital-twin simulation, inventory positioning, public information views, and direct integration with approved aviation systems.

### Out of scope

Direct control of aircraft, vehicles, bridges, or road infrastructure; replacement of official disaster command structures; and any guarantee that a predicted route is safe.

## 6. Business Processes

### Standard delivery

1. An authorized facility or official creates a request with commodity, quantity, destination, urgency, due time, stock, and receiving contact.
2. The system validates and prioritizes the request using criticality, affected population, stockout risk, isolation, and urgency.
3. The control room reviews affected areas and supply availability.
4. The route engine calculates the shortest route and feasible alternatives.
5. An authorized dispatcher approves, modifies, rejects, or defers a recommendation with a reason.
6. The driver receives the latest approved plan.
7. GPS, checkpoint, and field updates refresh progress.
8. The receiver confirms quantity, condition, and time.
9. Outcome and delay reason are stored for learning and reporting.

### Disruption response

An incident from a field user, authority, or integration is validated for location, timestamp, evidence, source reliability, and freshness. The affected road or bridge state is updated, active deliveries are re-evaluated, and alerts identify affected requests, alternatives, and recommended actions.

### Unreachable village

If a bridge is blocked and no safe road route exists, the system identifies nearby reachable villages and available receiving capacity. For life-critical requests it creates an air-delivery escalation for authorized human approval; it does not control aircraft automatically.

## 7. Functional Requirements

### Governance

- **FR-001:** Authenticate users and enforce role- and district-scoped access.
- **FR-002:** Support control-room officers, dispatchers, field officials, drivers, village representatives, receivers, and administrators.
- **FR-003:** Audit creation, update, override, approval, dispatch, alert, synchronization, and closure actions.
- **FR-004:** Configure districts, languages, thresholds, source reliability, notification channels, and escalation contacts.

### Network, GIS, and incidents

- **FR-005:** Maintain GIS entities for districts, villages, facilities, roads, bridges, hubs, helipads, and restricted areas.
- **FR-006:** Display accessibility with timestamp, source, confidence, evidence, and freshness.
- **FR-007:** Support landslide, flood, rainfall, bridge blockage, road damage, congestion, accident, and infrastructure-failure incidents.
- **FR-008:** Preserve conflicting reports and flag them for review rather than silently overwriting them.
- **FR-009:** Expire stale accessibility information using configurable freshness rules.

### Risk and prediction

- **FR-010:** Ingest weather, terrain, road, historical, GPS, and field-report signals through adapters.
- **FR-011:** Calculate risk band, probability, time window, confidence, and contributing factors.
- **FR-012:** Forecast probable disruption windows where data supports it and label forecasts advisory.
- **FR-013:** Distinguish predicted, reported, verified, and manually overridden states.
- **FR-014:** Require review when confidence is low, sources conflict, or emergency air delivery is proposed.

### Supply and prioritization

- **FR-015:** Create and update supply requests with commodity, quantity, destination, urgency, due time, stock, and service criticality.
- **FR-016:** Rank requests using configurable criticality, affected population, stockout risk, isolation, urgency, and local supply.
- **FR-017:** Allow priority overrides with a mandatory reason.
- **FR-018:** Identify requests that can be consolidated through a shared handoff hub.

### Route and dispatch

- **FR-019:** Calculate the shortest-distance route and one or more alternatives where feasible.
- **FR-020:** Show distance, ETA, expected delay, risk, confidence, vehicle constraints, and blocked segments.
- **FR-021:** Support emergency, urgent, routine, and wait-when-safe profiles.
- **FR-022:** Compare waiting for a safer window with taking a longer route for routine deliveries.
- **FR-023:** Support multi-stop plans, shared hubs, local carriers, nearby reachable villages, and pre-event delivery-and-return plans.
- **FR-024:** Allow authorized approval, rejection, modification, deferral, and reasoned override.

### Tracking, offline field work, and alerts

- **FR-025:** Track assigned vehicles through GPS when available.
- **FR-026:** Capture offline location, time, photos, notes, road status, and delivery evidence.
- **FR-027:** Synchronize offline records idempotently after reconnection.
- **FR-028:** Show last approved plan, last sync time, and stale-plan warnings offline.
- **FR-029:** Support checkpoint relay records for low-connectivity corridors.
- **FR-030:** Alert on blocked roads, rising risk, inaccessible locations, stalled deliveries, missed ETAs, and unresolved incidents.
- **FR-031:** Support acknowledgement, retry, escalation, multilingual templates, and minimum-necessary message content.

### Reporting and integrations

- **FR-032:** Show district connectivity, critical requests, bottlenecks, incidents, active vehicles, and emergency routes.
- **FR-033:** Export authorized reports and machine-readable data.
- **FR-034:** Integrate weather, GIS, road, GPS, messaging, and government systems through versioned adapters.
- **FR-035:** Provide documented APIs for approved monitoring systems with source attribution and health status.

## 8. Non-Functional Requirements

- **NFR-001 Availability:** Target 99.5% monthly availability during pilot operations.
- **NFR-002 Performance:** Common dashboard views under 3 seconds; normal route calculations under 30 seconds.
- **NFR-003 Resilience:** Mobile capture supports at least 72 hours of normal offline use.
- **NFR-004 Security:** Encryption in transit and at rest, least privilege, secure secrets, backups, and recovery procedures.
- **NFR-005 Privacy:** Collect operationally necessary personal data only; define retention and deletion before production.
- **NFR-006 Explainability:** Every recommendation shows inputs, timestamp, confidence, model/policy version, and reason.
- **NFR-007 Safety:** Predictions are advisory; high-risk dispatch and air delivery require human approval.
- **NFR-008 Localization:** Configurable language, units, dates, and notification templates.
- **NFR-009 Observability:** Logs, metrics, traces, source health, synchronization status, and model metrics.
- **NFR-010 Scalability:** Expand from pilot districts to NER states without changing domain boundaries.

## 9. Decision Policy

The MVP uses an explainable policy:

`delivery utility = urgency benefit - travel delay cost - route risk cost - failure cost - resource cost`

Hard constraints always apply: active closure, vehicle restriction, unsafe authority status, unavailable bridge, or missing air-delivery approval. Configurable weights cannot bypass these constraints.

| Condition | Recommendation |
|---|---|
| Emergency with safe road route | Dispatch the fastest feasible safe route |
| Emergency with no safe road route | Escalate air delivery or reachable-village handoff |
| Urgent with acceptable alternative | Use alternate and communicate delay |
| Routine with high risk | Wait or use safer route based on ETA comparison |
| Routine with low risk and very long alternative | Use shortest route with monitoring |
| Multiple aligned requests | Consolidate via hub or coordinated local pickup |
| No connectivity | Follow last synchronized plan and relay procedure |

## 10. Data Requirements

Core entities include users, roles, districts, villages, facilities, road segments, bridges, hubs, helipads, vehicles, drivers, supply requests, inventory snapshots, deliveries, route plans, route options, incidents, accessibility assessments, field reports, weather observations, alerts, synchronization batches, audit events, and model predictions.

Every observation must carry `source`, `captured_at`, `received_at`, `location`, `confidence`, `fresh_until`, `evidence`, and `review_state`.

## 11. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Sparse historical data | Begin with rules and calibrated heuristics; learn from verified outcomes |
| False prediction causes unsafe dispatch | Hard closures, human approval, confidence display, conservative fallback |
| Outdated map/road state | Freshness expiry, field confirmation, source ranking, conflict review |
| Connectivity failure | Offline app, sync queue, checkpoint relay, configured fallback channels |
| Integration instability | Adapter boundary, retries, health dashboards, manual import fallback |
| Low adoption | Fast role-specific workflows, local languages, training, useful reports |
| Sensitive data exposure | RBAC, encryption, audit, minimal projections, retention controls |

## 12. MVP Acceptance Criteria

An evaluator can create a medicine request, see the affected village prioritized, compare shortest and alternate routes, view risk and ETA explanations, choose dispatch/wait/reroute/handoff/escalation, track a vehicle, submit an offline photo-backed road-block report, synchronize it, trigger an alert, recalculate affected deliveries, complete proof of delivery, and inspect the full audit record.

## 13. Assumptions and Open Questions

- **[ASSUMPTION]** The pilot begins with selected districts and representative corridors.
- **[ASSUMPTION]** Participating authorities can provide authorized road, bridge, facility, contact, and emergency data.
- **[ASSUMPTION]** External providers permit the required operational use and caching.
- Which departments own final route-closure and air-delivery approval?
- Which languages, integrations, retention rules, pilot districts, and response SLAs are required?
- What evidence is sufficient to mark a road blocked or reopened?

## 14. Delivery Phases

1. **Demonstrator:** seeded GIS data, simulated weather/incidents, requests, priorities, alternatives, dashboard, and audit.
2. **Pilot:** field app, offline sync, GPS, verified reports, alerts, multilingual messages, and handoff workflows.
3. **Expansion:** calibrated hazard models, imagery, infrastructure analytics, integrations, and multi-state scaling.
