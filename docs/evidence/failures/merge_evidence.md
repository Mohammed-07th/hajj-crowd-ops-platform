# Deliverable 2 — MERGE evidence (silver_service_requests)

Business key: `request_id`. Bronze holds every lifecycle transition (~4-6 per request);
the staging set is deduplicated to the latest event per key before the MERGE, otherwise
Delta raises "Multiple source rows matched the same target row".

## Wave 1 — partial lifecycles (6,000 messages)
```
bronze_rows: 5585  ->  staged_rows: 2490  ->  silver rows: 2490
merge_metrics: {"num_target_rows_inserted": 2490, "num_target_rows_updated": 0, "first_load": true}

status distribution AFTER wave 1:
  ACKNOWLEDGED  1375
  DISPATCHED     867
  CANCELLED      154
  REPORTED        94
```

## Wave 2 — same seed, full lifecycles (11,868 messages)

Re-running the producer with the same `--seed` re-emits the SAME `request_id`s with further
lifecycle progress. That is what makes this an upsert rather than an append.

```
status distribution AFTER wave 2 (MERGE applied):
  RESOLVED        1945
  CANCELLED        376
  ON_SITE          155
  DISPATCHED        12
  ACKNOWLEDGED       9
  REPORTED           3

rows: 2500   distinct request_id: 2500
-> one row per request holding its CURRENT state; uniqueness proves upsert, not append.

PII governance:
  raw pilgrim_ref column present?    False
  raw reporter_phone column present? False
  hashed columns: ['pilgrim_ref_hash', 'reporter_phone_hash']
```
