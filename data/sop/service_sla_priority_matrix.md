---
doc_code: SOP-OPS-001
doc_title: Service Request Priority and SLA Matrix
version: 1.0
owner: Operations Directorate
supersedes: none
related: SOP-MED-002, SOP-SEC-007, SOP-OPS-006, SOP-OPS-020, SOP-SAN-003
---

> **Synthetic training material.** All operational data in this project is
> synthetic, generated for training purposes. Zone capacities, SLA targets and
> standard operating procedures are illustrative constructions and do not
> represent official figures or procedures of any Saudi authority.

# SOP-OPS-001 — Service Request Priority and SLA Matrix

## 1. Purpose

Defines the priority assigned to each category of field service request and the
response and resolution targets that apply. Every service request raised in the
operations platform is measured against this matrix.

## 2. Definitions

- **Response time** — minutes from `reported_at` until the request is
  **acknowledged** by a crew or controller. It measures whether anyone has taken
  ownership, not whether the problem is fixed.
- **Resolution time** — minutes from `reported_at` until the request reaches
  **RESOLVED**. A request that is acknowledged in one minute and resolved in
  four hours has met its response target and breached its resolution target;
  both are reported separately.
- **Breach** — actual time exceeds the target. Breaches are counted, not
  averaged away.

## 3. The SLA matrix

| Category | Priority | Response target (min) | Resolution target (min) |
|---|---|---|---|
| MEDICAL | P1 | **4** | **30** |
| MEDICAL | P2 | 10 | 60 |
| CROWD_PRESSURE | P1 | **3** | **20** |
| CROWD_PRESSURE | P2 | 8 | 45 |
| SECURITY | P1 | **5** | **40** |
| LOST_PERSON | P2 | 10 | 120 |
| LOST_PERSON | P3 | 20 | 180 |
| WATER | P3 | 30 | 90 |
| SANITATION | P4 | 60 | 240 |
| WAYFINDING | P4 | 15 | 60 |

**The response-time SLA for a P1 medical request is 4 minutes**, with a
resolution target of 30 minutes. This is the tightest medical target and it
exists because the P1 medical definition in SOP-MED-002 is limited to
life-threatening presentations.

**CROWD_PRESSURE P1 carries the tightest response target of any category at
3 minutes**, shorter even than P1 medical. A crowd-pressure incident that is not
addressed within minutes generates casualties faster than any single medical case.

## 4. Priority assignment

Priority is assigned at the point of reporting and may be **raised** by any
controller but **lowered** only by a Sector Supervisor or above.

| Priority | Meaning |
|---|---|
| P1 | Immediate threat to life or to crowd safety |
| P2 | Urgent; harm likely if not addressed within the hour |
| P3 | Standard; degrades service quality |
| P4 | Routine; scheduled or opportunistic |

Not every category carries every priority. **SECURITY is P1 only** — a security
request that does not meet the P1 threshold is logged as an observation under
SOP-OPS-020 rather than raised as a service request. WATER is P3 only,
SANITATION and WAYFINDING are P4 only.

## 5. Lifecycle

Every request progresses through:

`REPORTED → ACKNOWLEDGED → DISPATCHED → ON_SITE → RESOLVED`

`CANCELLED` is reachable from any non-terminal state. A crew identifier is
mandatory from `DISPATCHED` onward — a dispatched request with no crew assigned
is a data integrity failure and is rejected at ingestion. `RESOLVED` requires a
resolution timestamp.

Dispatch rules and handover are defined in SOP-OPS-006.

## 6. Escalation on breach

| Condition | Action |
|---|---|
| P1 response target exceeded | Automatic notification to SOC Controller |
| P1 resolution target exceeded by 50% | Duty Operations Director informed |
| Any P2 exceeding double its resolution target | Sector Supervisor review at handover |
| Zone-level breach rate above **15%** in any rolling hour | Treated as a resourcing incident under SOP-OPS-020 |

## 7. Measurement

Breach rates are computed per zone, category and priority, and reviewed at each
shift handover under SOP-OPS-006. Targets in this document are the single source
of truth: the operations platform's SLA reference data is derived from this
matrix and must match it exactly. A discrepancy between the two is a reportable
defect.

---

*Targets are illustrative constructions for this training project, informed by
general emergency-response practice. They are not official policy of any
authority.*
