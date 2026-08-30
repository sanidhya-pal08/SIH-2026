---
title: NER Sahayak
created: 2026-08-29
updated: 2026-08-29
status: draft
---

# PRD: NER Sahayak
*Working title — confirm.*

## 0. Document Purpose
This PRD defines the minimum viable product for NER Sahayak, a logistics and accessibility intelligence platform for the North Eastern Region. It is intended for product, operations, engineering, and government stakeholders who need a common operational picture for road conditions, delivery risk, emergency response, and field reporting. This document builds on the business requirements and architecture already captured in [BRD.md](BRD.md) and [ARCHITECTURE-AND-SYSTEM-DESIGN.md](ARCHITECTURE-AND-SYSTEM-DESIGN.md); it does not duplicate those artifacts verbatim.

## 1. Vision
NER Sahayak helps authorities move essential goods safely and quickly across difficult terrain by combining live road status, weather, risk signals, and delivery demand into one decision-making workflow. The product gives control rooms and field teams a shared operational picture so they can decide what to send, where to send it first, and when to wait, reroute, consolidate, or escalate.

The core product is not a route-optimization toy; it is an operational decision support system for fragile logistics conditions. In a region affected by landslides, floods, delayed connectivity, and damaged roads, every recommendation must be explainable, fresh, and accountable to human operators. The product will help reduce avoidable delays, improve safety, and create evidence for better infrastructure decisions over time.

## 2. Target User

### 2.1 Jobs To Be Done
- District control-room officers need to see road accessibility, active supply needs, and risk before they dispatch a vehicle.
- Dispatchers need to compare route options, approve or override recommendations, and track changes in delivery status.
- Field officers need to report road blockages, verify conditions, and submit proof of delivery even in low-network settings.
- Drivers and local carriers need clear route instructions, safety warnings, and a way to update progress without constant connectivity.
- Village and facility representatives need a simple way to request support and confirm that deliveries arrived.
- Administrators need operational governance, source confidence, audit trails, and configurable thresholds.

### 2.2 Non-Users (v1)
This v1 is not intended for fully autonomous dispatching, public-facing consumer logistics, or direct control of aircraft, road infrastructure, or emergency services. The system is an operational support tool for authorized officials, not a replacement for command authority.

### 2.3 Key User Journeys

- UJ-1. Control room prioritizes a critical medicine request during a flood event.
  - Persona + context: District operations officer receives a stockout alert from a hospital while roads are deteriorating.
  - Entry state: Officer is logged in to the dashboard and sees affected villages and active incidents.
  - Path: Reviews supply request, checks accessibility states, inspects route alternatives, compares urgency and risk, approves a dispatch or alternate plan.
  - Climax: Recommendation shows why the selected route is preferred and what is blocked.
  - Resolution: Request is assigned and visible to the driver and monitoring team.

- UJ-2. Field officer submits a bridge blockage report from a low-connectivity corridor.
  - Persona + context: Field official is on-site with limited mobile signal after heavy rainfall.
  - Entry state: Officer is offline and has a cached plan with last-known road status.
  - Path: Captures location, photos, road condition, and timestamp; syncs the report when connectivity returns.
  - Climax: The report updates road status and triggers re-evaluation of affected deliveries.
  - Resolution: Dispatch team sees the change, re-routes affected vehicles, and updates field alerts.

- UJ-3. Driver receives an alternate route with a clear safety policy.
  - Persona + context: Driver is assigned a supply trip with a blocked corridor and a safer alternative route.
  - Entry state: Driver has an approved plan in the mobile app.
  - Path: Views route options, ETA, risk explanation, and any wait-for-safe-window advice.
  - Climax: Driver confirms or rejects the assignment and captures checkpoint updates.
  - Resolution: Control room sees progress, delays, and final delivery confirmation.

## 3. Glossary
- Accessibility state — Operational condition of a road, bridge, or corridor, such as open, restricted, hazardous, blocked, or unknown.
- Delivery request — A request for medicine, food, or supplies that includes destination, urgency, commodity, and quantity.
- Dispatch decision — The selected action for a goods movement, such as dispatch, reroute, defer, handoff, or escalate.
- Freshness — The recency of the data and whether it remains valid for operational use.
- Route alternative — A candidate path that differs from the shortest route and may trade travel time for safety or reliability.
- Source confidence — A measure of how trustworthy the input event or report is, along with evidence quality.
- Safety gate — A hard policy guard that blocks unsafe routes or actions, such as active closures or vehicle restrictions.
- Proof of delivery — Evidence that a package or supply was delivered, including time, quantity, and receiving confirmation.

## 4. Features

### 4.1 Operational Visibility and Risk Picture
**Description:** The system shows the current state of accessibility, incidents, active deliveries, and supply needs in the monitored districts. It aggregates live and delayed information from multiple sources and highlights anomalies requiring action. Realizes UJ-1 and UJ-2.

**Functional Requirements:**

#### FR-1: Shared district operating view
The system shall show current accessibility, active requests, incidents, and vehicle status for authorized users by district and corridor. Realizes UJ-1.

**Consequences (testable):**
- Dashboard view lists active blocked, restricted, and hazardous corridors with source and freshness labels.
- User can filter by district, route, incident type, or response priority.

#### FR-2: Incident and evidence capture
The system shall allow users to create and review incidents with location, timestamp, evidence, source, confidence, and review state. Realizes UJ-2.

**Consequences (testable):**
- A field report can include photo evidence, notes, and a location timestamp.
- Conflicting reports remain visible and require review rather than silent overwriting.

#### FR-3: Freshness and confidence display
The system shall surface timestamps, source, confidence, and freshness for all operational data. Realizes UJ-1.

**Consequences (testable):**
- Each accessibility update shows when it was captured and when it expires.
- Stale or low-confidence data is clearly labeled as advisory.

### 4.2 Request Intake and Prioritization
**Description:** Authorized users create supply requests and the system ranks them according to urgency, criticality, affected population, stock risk, isolation, and available local supply. Realizes UJ-1.

**Functional Requirements:**

#### FR-4: Request creation and tracking
The system shall allow authorized users to create, edit, and monitor supply requests with destination, urgency, commodity, quantity, and service criticality. Realizes UJ-1.

**Consequences (testable):**
- Request records include due time, receiving contact, and operational priority.
- Updates preserve the audit trail for each request.

#### FR-5: Priority scoring and override
The system shall calculate a configurable priority score and allow a justified override with reason capture. Realizes UJ-1.

**Consequences (testable):**
- Priority ranking can consider criticality, affected population, stockout risk, isolation, urgency, and local availability.
- Overrides require a mandatory reason and approval state.

#### FR-6: Hub and consolidation support
The system shall identify where requests can be consolidated through shared handoff hubs or nearby reachable villages. Realizes UJ-1.

**Consequences (testable):**
- A grouped delivery plan can show consolidation opportunities and handoff route logic.
- Shared deliveries are linked to the originating requests and final proof of delivery.

### 4.3 Route Planning and Dispatch
**Description:** The system evaluates route alternatives against safety constraints, vehicle capabilities, risk, distance, and timing to recommend the best course of action for dispatch. Realizes UJ-1 and UJ-3.

**Functional Requirements:**

#### FR-7: Feasible route alternatives
The system shall calculate the shortest feasible route and one or more alternatives when conditions allow. Realizes UJ-1.

**Consequences (testable):**
- Each route option displays distance, ETA, expected delay, risk, confidence, and blocked segments.
- Closed roads, unsafe bridges, and vehicle restrictions are excluded before ranking.

#### FR-8: Dispatch decision profiles
The system shall support emergency, urgent, routine, and wait-when-safe decision profiles. Realizes UJ-1.

**Consequences (testable):**
- Dispatcher can choose to dispatch, reroute, wait, defer, or escalate based on route conditions.
- The system explains why a recommended action is safer or faster.

#### FR-9: Human approval gates
The system shall require human approval for high-risk or potentially unsafe dispatch actions, including emergency air-delivery escalation. Realizes UJ-1.

**Consequences (testable):**
- Unsafe actions remain blocked until approved by an authorized role.
- Any override is visible in the audit record.

### 4.4 Offline Field Work, Tracking, and Delivery Evidence
**Description:** Drivers and field agents can capture progress, photos, checkpoints, and delivery confirmations even when connectivity is poor. The system later reconciles this data when service returns. Realizes UJ-2 and UJ-3.

**Functional Requirements:**

#### FR-10: Offline-first mobile workflow
The system shall support the collection of route updates, location notes, photos, and road status offline. Realizes UJ-2.

**Consequences (testable):**
- User can record and queue updates when network is unavailable.
- App shows last synced time and stale plan warnings when offline.

#### FR-11: Tracking and checkpoint relay
The system shall track assigned vehicles using GPS when available and support checkpoint relay records for low-connectivity corridors. Realizes UJ-3.

**Consequences (testable):**
- Each checkpoint includes timestamp, location, and relevant status update.
- GPS and manual inputs are distinguishable in the audit trail.

#### FR-12: Proof of delivery and closure
The system shall record delivery confirmation, quantity received, conditions, and closure details for requests and deliveries. Realizes UJ-3.

**Consequences (testable):**
- Receiver can confirm receipt and note discrepancies or delays.
- Delivery outcome remains linked to the request and route history.

### 4.5 Alerts, Notifications, and Reporting
**Description:** The system sends operational alerts, supports acknowledgement and escalation, and produces reports suitable for district operations and governance. Realizes UJ-1.

**Functional Requirements:**

#### FR-13: Alerting and escalation
The system shall alert on blocked roads, rising risk, stalled deliveries, missed ETAs, and unresolved incidents, with acknowledgement and escalation support. Realizes UJ-1.

**Consequences (testable):**
- Alert recipients can acknowledge, retry, or escalate a case.
- Notification templates support multilingual delivery and channel-specific fallback.

#### FR-14: Operational reporting and exports
The system shall provide district summaries, active bottlenecks, emergency routes, and exports for authorized reports and integrations. Realizes UJ-1.

**Consequences (testable):**
- Users can review connectivity, requests, incidents, and vehicle status by district.
- Exported data is machine-readable and source-attributed.

## 5. Non-Goals (Explicit)
- The product will not autonomously control aircraft, infrastructure, or road operations.
- The product will not replace formal disaster-command structures or legal authority for emergency decisions.
- The product will not guarantee a route is safe under all conditions; it provides advisory guidance and explainability.
- The product will not attempt full public-facing citizen logistics management in v1.
- The product will not centralize all historical data science features in the initial release.

## 6. MVP Scope

### 6.1 In Scope
- Web-based control-room dashboard for district logistics visibility.
- Offline-first mobile field app for reporting and updates.
- GIS-backed accessibility and incident tracking for roads, bridges, villages, and facilities.
- Supply request intake, prioritization, and approval workflows.
- Route alternatives based on risk, delay, reliability, and vehicle constraints.
- Alerting, acknowledgment, and escalation with multilingual support.
- Proof of delivery and operational audit trail.
- Configurable thresholds, source confidence, and role-based access.

### 6.2 Out of Scope for MVP
- Public portal or citizen self-service application.
- Advanced satellite imagery analysis and automated damage classification.
- Full autonomous AI decision making for dispatch.
- Direct integration with all government systems and aviation controls.
- Large-scale predictive modeling beyond advisory guidance and rules-based thresholds.

## 7. Success Metrics

**Primary**
- SM-1: Time-to-critical-response — median time from a request or disruption to operator decision for high-priority cases. Target: within 15 minutes during pilot conditions.
- SM-2: Delivery completion rate for priority requests — percentage of critical and urgent requests delivered without material delay. Target: > 90% in pilot districts.
- SM-3: Road status accuracy for verified incidents — percentage of reported disruptions validated by field evidence or authoritative update. Target: > 85%.

**Secondary**
- SM-4: Offline reporting success — percentage of field submissions successfully captured and synchronized after reconnect. Target: > 95%.
- SM-5: Alert acknowledgement rate — percentage of alerts acknowledged by assigned stakeholders within policy threshold. Target: > 90%.

**Counter-metrics**
- SM-C1: Unsafe override rate — number of route approvals that bypass safety constraints or later require correction. Must remain near zero.
- SM-C2: False urgency inflation — rate at which routine requests are over-ranked as critical. Must remain low enough to avoid operational noise.

## 8. Open Questions
1. Which departments hold final approval authority for road closure decisions and air-delivery escalation?
2. Which pilot districts and corridors are in scope for the initial deployment?
3. Which languages and notification channels are required for each district?
4. What evidence standard is required to mark a corridor blocked or reopened?
5. What retention policy and personal-data minimization rules will apply to operational records?
6. What external data sources and hosting arrangements are permitted for pilot operations?

## 9. Assumptions Index
- [ASSUMPTION] The pilot begins with selected districts and representative routes.
- [ASSUMPTION] Participating departments can provide current road, bridge, facility, vehicle, and contact data.
- [ASSUMPTION] External data providers permit operational use, caching, and appropriate provenance tracking.
- [ASSUMPTION] Human operators remain accountable for final dispatch and escalation decisions.

## 10. Implementation Notes
The MVP should be built as a modular system with a clear separation between operational data, route intelligence, and field reporting. The product should favor explainability and accountability over opaque optimization. Until enough historical evidence exists, rule-based scoring and constrained routing should remain the production decision path, with AI used as an advisory layer only.
