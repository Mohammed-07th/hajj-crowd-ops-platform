---
doc_code: SOP-OPS-020
doc_title: Incident Reporting and Escalation Matrix
version: 1.0
owner: Operations Directorate
supersedes: none
related: SOP-CS-004, SOP-CS-011, SOP-MED-002, SOP-SEC-007, SOP-OPS-006
---

> **Synthetic training material.** All operational data in this project is
> synthetic, generated for training purposes. Zone capacities, SLA targets and
> standard operating procedures are illustrative constructions and do not
> represent official figures or procedures of any Saudi authority.

# SOP-OPS-020 — Incident Reporting and Escalation

## 1. Purpose

Defines incident severity levels, who must be informed at each level, and how
long records are retained. Other procedures refer here whenever they say
"report under SOP-OPS-020".

## 2. Severity levels

| Severity | Definition | Examples |
|---|---|---|
| **S1 — Critical** | Life lost or imminent risk to multiple lives; site-wide service failure | Crowd collapse, structural failure, mass casualty, full evacuation |
| **S2 — Major** | Serious injury, or an incident requiring cross-agency response | P1 medical with multiple casualties, zone at SEVERE utilisation, missing child past the 30-minute timer, security threat |
| **S3 — Moderate** | Contained incident with service impact | Zone sustained above 90%, medical point unable to accept T1, water station failure during heat Level 2 |
| **S4 — Minor** | Logged for trend analysis; no immediate escalation | Sensor fault, signage damage, isolated SLA breach |

## 3. Notification matrix — who is informed

| Severity | Informed immediately | Informed within 30 min | Informed at handover |
|---|---|---|---|
| **S1** | Duty Operations Director, Civil Defence Liaison, SOC Controller, all Sector Supervisors | Directorate leadership | All staff |
| **S2** | SOC Controller, Duty Operations Director, **Civil Defence Liaison** | Relevant directorate (Medical / Security) | All Sector Supervisors |
| **S3** | Sector Supervisor, SOC Controller | Duty Operations Director | Relevant directorate |
| **S4** | Zone Marshal, Sector Supervisor | — | Sector Supervisor |

**A P1 security incident is severity S2 at minimum.** That means the **SOC
Controller, the Duty Operations Director and the Civil Defence Liaison are all
informed immediately**, the Security Directorate is informed within 30 minutes,
and all Sector Supervisors are briefed at handover. Where the security incident
involves a threat to multiple lives it is S1, and directorate leadership is added.

Security requests are P1 only (see **SOP-OPS-001** section 4), so every security
service request raised on the platform triggers at least the S2 chain.

## 4. Reporting timeline

| Step | Deadline |
|---|---|
| Verbal notification to the first role in the matrix | Immediate |
| Incident record opened in the operations platform | Within 15 minutes |
| Initial written summary | Within 2 hours (S1/S2), next handover (S3/S4) |
| Full incident report | 24 hours (S1/S2), 72 hours (S3) |
| Review and lessons recorded | Next shift review under SOP-OPS-006 |

An unacknowledged notification is escalated by voice within **90 seconds**,
consistent with **SOP-CS-011** section 4. Silence is never acknowledgement.

## 5. Mandatory reportable events

The following are always reported regardless of outcome:

- Any zone sustained above **90%** utilisation (see **SOP-CS-004**)
- Any evacuation or diversion authorised under **SOP-CS-011**
- Any ambulance corridor activation under **SOP-MED-002**
- Any missing-person case reaching the 30-minute timer under **SOP-SEC-007**
- Any heat Level 2 activation or above under **SOP-MED-009**
- Any medical point unable to accept T1 patients
- Any zone whose sensors are degraded or offline for more than **5%** of
  readings in an hour
- Any zone-level SLA breach rate above **15%** in a rolling hour

The last two are detected automatically from platform metrics rather than
reported by staff. Automatic detection does not remove the requirement to
acknowledge and act.

## 6. Record contents

Every incident record contains: incident identifier, severity, site and zone,
time of onset, time of detection, time of first notification, roles notified
with acknowledgement times, actions taken, authorising roles, resolution time,
and outcome.

Where an incident involves personal data — a missing person's details, a
patient's identifiers — that data is stored against the incident record with
restricted access and is **not** propagated into analytical datasets. Analytical
copies carry hashed identifiers only.

## 7. Retention

| Severity | Retention |
|---|---|
| S1 | 10 years |
| S2 | 5 years |
| S3 | 2 years |
| S4 | 12 months |

Records containing personal data are reviewed at the retention boundary and the
personal fields are removed while the operational record is kept.

---

*Severity tiers and notification structure follow standard incident-command
practice. Illustrative constructions for this training project; not official
policy of any authority.*
