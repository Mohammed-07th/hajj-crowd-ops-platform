---
doc_code: SOP-CS-011
doc_title: Zone Capacity Escalation and Diversion Authority
version: 1.0
owner: Site Operations Centre
supersedes: none
related: SOP-CS-004, SOP-CS-015, SOP-OPS-020, SOP-OPS-006
---

> **Synthetic training material.** All operational data in this project is
> synthetic, generated for training purposes. Zone capacities, SLA targets and
> standard operating procedures are illustrative constructions and do not
> represent official figures or procedures of any Saudi authority.

# SOP-CS-011 — Zone Capacity Escalation and Diversion Authority

## 1. Purpose

**SOP-CS-004** defines *when* a zone must escalate. This document defines *who
may act* at each level, what they are permitted to authorise, and who must be
told. It is the authority matrix, not the detection procedure.

No diversion, closure or evacuation is valid without the authorisation named in
section 3. A marshal who diverts a crowd without authority creates an
uncontrolled secondary flow, which is more dangerous than the original density.

## 2. Roles

| Role | Scope | Location |
|---|---|---|
| Zone Marshal | One zone | On the floor |
| Sector Supervisor | 3–6 adjacent zones | Sector post |
| Site Operations Centre (SOC) Controller | One site | SOC |
| Duty Operations Director | All sites | SOC, command desk |
| Civil Defence Liaison | Cross-agency | SOC, co-located |

## 3. Authority matrix

| Utilisation state | Action permitted | Authorising role | Must be notified |
|---|---|---|---|
| ELEVATED (70–79%) | Increase marshal presence, open reserve lanes | **Zone Marshal** | Sector Supervisor |
| HIGH (80–89%) | Throttle inflow at feeder gates; hold groups at staging points | **Sector Supervisor** | SOC Controller |
| CRITICAL (90–94%) | Stop inflow entirely; open contraflow egress; divert arriving flow to an alternate zone | **SOC Controller** | Duty Operations Director, Civil Defence Liaison |
| SEVERE (95%+) | Mandatory diversion; partial or full zone closure | **Duty Operations Director** | Civil Defence Liaison, all Sector Supervisors |
| Evacuation | Full evacuation of a zone or site | **Duty Operations Director** jointly with **Civil Defence Liaison** | All roles; see SOP-CS-015 |

**The single most asked question at handover:** diversion at the CRITICAL
threshold (90%) is authorised by the **SOC Controller**. Full closure at SEVERE
(95%) requires the **Duty Operations Director**. Evacuation always requires the
Duty Operations Director *and* the Civil Defence Liaison acting jointly — one
signature is not sufficient.

## 4. Notification chain

Notification is sequential and each step is acknowledged before the next:

1. Zone Marshal → Sector Supervisor (radio, channel per sector)
2. Sector Supervisor → SOC Controller (SOC log entry, timestamped)
3. SOC Controller → Duty Operations Director (direct, in person or command line)
4. Duty Operations Director → Civil Defence Liaison

An unacknowledged notification must be escalated by voice within **90 seconds**.
Silence is never treated as acknowledgement.

## 5. Hold points

A **hold point** is a decision that cannot be delegated downward and must be
recorded before action:

- **HP-1** — Before inflow is stopped at CRITICAL: confirm at least one egress
  route is clear and staffed. Stopping inflow into a zone with a blocked exit
  converts a density problem into a trap.
- **HP-2** — Before diversion: confirm the receiving zone is below 70%
  utilisation. Diverting into an already-HIGH zone transfers the incident rather
  than resolving it.
- **HP-3** — Before closure: confirm wayfinding staff are positioned at every
  approach to the closed zone, with signage in Arabic and English at minimum.
- **HP-4** — Before reopening: two consecutive readings below 70% at least
  **10 minutes apart**, plus marshal visual confirmation.

## 6. Sustained-threshold requirement

Authority is triggered by *sustained* exceedance as defined in SOP-CS-004
section 3.1, not by a single reading:

- 90% sustained **5 minutes** → SOC Controller assumes control of the zone.
- 95% at any single reading → Duty Operations Director is notified immediately,
  with no sustaining period.

A zone that has been above 90% for **12 minutes** is well past the escalation
trigger: the SOC Controller should already hold control, inflow should already
be stopped, and the Duty Operations Director should already have been notified.
If any of those has not happened, treat it as a reportable failure under
SOP-OPS-020.

## 7. Records and review

Every escalation to CRITICAL or above generates an incident record containing:
zone ID, timestamp of first threshold breach, sustained minutes above threshold,
peak utilisation, authorising role, hold points cleared, and time to
de-escalation. Records are reviewed at the next shift handover under SOP-OPS-006
and retained per SOP-OPS-020.

---

*Thresholds referenced here are defined in SOP-CS-004 and are informed by Fruin's
pedestrian level-of-service bands. Illustrative constructions for this training
project; not official policy of any authority.*
