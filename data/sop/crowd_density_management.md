---
doc_code: SOP-CS-004
doc_title: Crowd Density Management and Escalation Thresholds
version: 1.0
owner: Crowd Safety Directorate
supersedes: none
related: SOP-CS-011, SOP-CS-015, SOP-MED-009, SOP-OPS-020
---

> **Synthetic training material.** All operational data in this project is
> synthetic, generated for training purposes. Zone capacities, SLA targets and
> standard operating procedures are illustrative constructions and do not
> represent official figures or procedures of any Saudi authority.

# SOP-CS-004 — Crowd Density Management and Escalation Thresholds

## 1. Purpose and scope

This procedure defines how zone occupancy is monitored, what density levels
require intervention, and at which point control of a zone escalates from the
zone marshal to the Site Operations Centre. It applies to all monitored zones
across HARAM_MAKKAH, MINA, ARAFAT, MUZDALIFAH and the year-round tourism sites
at ALULA and DIRIYAH.

Authority to divert or close a zone is **not** granted by this document. That
authority is defined in **SOP-CS-011** (Zone Capacity Escalation and Diversion
Authority). This document defines when SOP-CS-011 must be invoked.

## 2. Density levels of service

Density is expressed as persons per square metre of usable circulation area.
The bands below follow Fruin's pedestrian level-of-service model.

| Band | Density (persons/m²) | Flow condition | Required action |
|---|---|---|---|
| A–B | below 1.0 | Free circulation | Routine monitoring |
| C | 1.0 – 1.9 | Constrained but self-regulating | Routine monitoring |
| D | 2.0 – 2.9 | Restricted, speed drops sharply | Marshal presence increased |
| E | 3.0 – 3.9 | Shuffling gait, counterflow impossible | Inflow throttling begins |
| F | **4.0 and above** | Involuntary contact, progressive crowd collapse risk | Immediate inflow stop and escalation under SOP-CS-011 |

**4.0 persons/m² is the critical threshold.** At and above this density,
individuals lose the ability to control their own movement and crowd-quake
propagation becomes possible. Threshold informed by Fruin's pedestrian
level-of-service bands and the widely cited 4–5 persons/m² danger range in
published crowd-science literature.

## 3. Occupancy thresholds against rated capacity

Where direct density measurement is unavailable, occupancy against rated zone
capacity is the operative proxy. The escalation ladder is:

| Utilisation | State | Action | Notify |
|---|---|---|---|
| below 70% | NORMAL | Routine monitoring at standard cadence | — |
| 70% – 79% | ELEVATED | Increase monitoring cadence; brief zone marshals | Zone Marshal |
| 80% – 89% | HIGH | Begin inflow throttling at feeder gates; stage reserve crew | Sector Supervisor |
| 90% – 94% | CRITICAL | Stop inflow; open all egress routes; invoke SOP-CS-011 | Site Operations Centre |
| 95% and above | SEVERE | Mandatory diversion; treat as incident under SOP-OPS-020 | Duty Operations Director |

### 3.1 Sustained-threshold rule

A single reading above a threshold is not an escalation trigger. Escalation is
triggered when a zone remains above the threshold for a **sustained period**:

- **80% sustained for 10 minutes** → escalate to HIGH.
- **90% sustained for 5 minutes** → escalate to CRITICAL and invoke SOP-CS-011.
- **95% at any single reading** → immediate SEVERE, no sustaining period.

This is why the operations dashboard reports `minutes_above_80pct` and
`minutes_above_90pct` per zone-hour rather than instantaneous occupancy alone.

## 4. Monitoring cadence

| State | Sensor polling | Marshal visual confirmation | Ops Centre review |
|---|---|---|---|
| NORMAL | every 10 seconds | every 30 minutes | hourly |
| ELEVATED | every 10 seconds | every 15 minutes | every 30 minutes |
| HIGH | every 10 seconds | every 5 minutes | continuous |
| CRITICAL / SEVERE | every 10 seconds | continuous | continuous, director present |

Visual confirmation is mandatory before any escalation above HIGH. Gate sensors
report estimated occupancy and can drift; a marshal confirms the estimate before
a diversion order is issued under SOP-CS-011.

## 5. Degraded sensor handling

A zone whose sensors report `DEGRADED` or `OFFLINE` for more than **5% of
readings in any hour** is treated as unmonitored. An unmonitored zone is
automatically held at **ELEVATED** state minimum, regardless of its last known
occupancy, until sensor coverage is restored. Report sensor faults under
SOP-OPS-020.

## 6. Interaction with heat stress

Density thresholds tighten under heat stress. When the WBGT index exceeds the
threshold defined in **SOP-MED-009**, the HIGH threshold in section 3 drops from
80% to **70%**, because heat casualties rise sharply where crowd density
prevents movement to shade or water.

## 7. Records

Every escalation above ELEVATED is logged as an incident record with zone ID,
timestamp, peak utilisation, sustained minutes above threshold, the authorising
role, and the action taken. Retention is defined in SOP-OPS-020.

---

*Thresholds in sections 2 and 3 are informed by Fruin's pedestrian
level-of-service bands and published Hajj crowd-science literature. They are
illustrative constructions for this training project and are not official policy
of any authority.*
