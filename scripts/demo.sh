#!/usr/bin/env bash
# Guided live demo. Run `make demo`, then press ENTER between steps.
#
# Each step prints what it proves before it runs, so you can talk over it.
# Nothing here rebuilds data — it reads what is already there, so it is fast
# and safe to run in front of an audience.
set -u
cd "$(dirname "$0")/.."

PY="./.venv/bin/python"
BOLD=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; RED=$'\033[31m'
YELLOW=$'\033[33m'; CYAN=$'\033[36m'; OFF=$'\033[0m'

step_no=0

banner() {
  step_no=$((step_no + 1))
  echo
  echo "${BOLD}${CYAN}════════════════════════════════════════════════════════════════════${OFF}"
  echo "${BOLD}${CYAN}  STEP $step_no — $1${OFF}"
  echo "${BOLD}${CYAN}════════════════════════════════════════════════════════════════════${OFF}"
  echo "${DIM}  $2${OFF}"
  echo
}

say() { echo "${YELLOW}  ▸ $1${OFF}"; }

pause() {
  # Only pause when there is a real terminal to read from. Piped or redirected
  # (`make demo | tee demo.log`) the script runs straight through instead of
  # failing on /dev/tty, which exists as a file even when nothing is attached.
  [ -t 0 ] || return 0
  echo
  echo "${DIM}  ── press ENTER for the next step (Ctrl-C to stop) ──${OFF}"
  read -r _ || true
}

# --------------------------------------------------------------------
echo
echo "${BOLD}  Hajj & Tourism Crowd Operations Data Platform — live demo${OFF}"
echo "${DIM}  8 steps, about 10 minutes with talking. Nothing is rebuilt.${OFF}"
echo

# --- preflight ------------------------------------------------------
echo "${BOLD}  Preflight${OFF}"
ok=1
if docker exec hajj-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1; then
  echo "   ${GREEN}✓${OFF} Kafka broker responding"
else
  echo "   ${RED}✗${OFF} Kafka not up      → run: make up"; ok=0
fi
if curl -s --max-time 4 http://localhost:6333/healthz >/dev/null 2>&1; then
  echo "   ${GREEN}✓${OFF} Qdrant responding"
else
  echo "   ${RED}✗${OFF} Qdrant not up     → run: make up"; ok=0
fi
if curl -s --max-time 4 -o /dev/null http://localhost:8080/health 2>/dev/null; then
  echo "   ${GREEN}✓${OFF} Airflow UI at http://localhost:8080  (admin / admin)"
else
  echo "   ${YELLOW}!${OFF} Airflow not up    → run: make airflow   (step 5 uses the browser)"
fi
if [ -d delta/gold_zone_hourly/_delta_log ]; then
  echo "   ${GREEN}✓${OFF} Lakehouse tables present"
else
  echo "   ${RED}✗${OFF} No lakehouse yet  → run: make pipeline"; ok=0
fi
if [ "$ok" -eq 0 ]; then
  echo
  echo "${RED}  Fix the above, then run 'make demo' again.${OFF}"
  exit 1
fi
pause

# --- 1 ---------------------------------------------------------------
banner "Nothing here is simulated" \
        "The rubric says a simulation earns nothing, so the build fails if I ever cheat."
say "Watch for: AUDIT PASSED"
bash scripts/verify_no_simulation.sh
pause

# --- 2 ---------------------------------------------------------------
banner "The contract rejects bad records" \
        "Deliverable 1. 100 events in, 20 deliberately malformed."
say "Watch for: 80 accepted / 20 rejected, and the strict-mode rejection at the end"
PYTHONPATH=. $PY scripts/demo_failures/demo_bad_records.py 2>/dev/null | tail -32
pause

# --- 3 ---------------------------------------------------------------
banner "The lakehouse: bronze, silver, gold" \
        "Deliverable 2. Two numbers matter: the MERGE collapse and the gold aggregation."
PYTHONPATH=. PYTHONUNBUFFERED=1 $PY -c "
from src.lakehouse import delta_io
rows = {}
for t in ['bronze_zone_occupancy','bronze_service_requests','silver_zone_occupancy',
          'silver_service_requests','gold_zone_hourly','quarantine']:
    rows[t] = delta_io.read(t).num_rows
    print(f'   {t:28s} {rows[t]:>9,} rows')
print()
print(f'   MERGE  : {rows[\"bronze_service_requests\"]:,} request events  ->  {rows[\"silver_service_requests\"]:,} current-state rows')
print(f'   GOLD   : {rows[\"silver_zone_occupancy\"]:,} readings  ->  {rows[\"gold_zone_hourly\"]:,} zone-hours  ({rows[\"silver_zone_occupancy\"]/rows[\"gold_zone_hourly\"]:.0f}:1)')
"
say "Say: one request sends 4-6 messages; MERGE keeps one row per request holding its CURRENT state"
say "Say: minutes_above_90pct exists only after grouping - no single sensor reading contains it"
pause

# --- 4 ---------------------------------------------------------------
banner "A bad write is actually refused" \
        "Deliverable 2. Breaking change refused; additive change accepted."
say "Watch for: 'Schema of data does not match table schema'"
PYTHONPATH=. $PY -m src.lakehouse.schema_demo 2>/dev/null | sed -n '/PART 1b/,$p'
pause

# --- 5 ---------------------------------------------------------------
banner "The quality gate stops the pipeline" \
        "Deliverables 4 and 5 - the strongest moment. Switch to the browser."
echo "   ${BOLD}Open:${OFF} http://localhost:8080  →  hajj_ops_pipeline  →  Graph"
echo "   ${BOLD}Select run:${OFF} gate2_failure_demo"
echo
echo "   The task states in that run:"
echo
printf "     %-30s ${GREEN}%s${OFF}\n"  "validate_bronze"             "success   (GATE 1 passed)"
printf "     %-30s ${GREEN}%s${OFF}\n"  "build_silver_occupancy"      "success"
printf "     %-30s ${GREEN}%s${OFF}\n"  "build_silver_requests_merge" "success"
printf "     %-30s ${RED}%s${OFF}\n"    "validate_silver"             "FAILED    (GATE 2)"
printf "     %-30s ${YELLOW}%s${OFF}\n" "build_gold_zone_hourly"      "upstream_failed  - never ran"
printf "     %-30s ${YELLOW}%s${OFF}\n" "refresh_rag_index"           "upstream_failed  - never ran"
printf "     %-30s ${YELLOW}%s${OFF}\n" "smoke_test_rag"              "upstream_failed  - never ran"
echo
say "Say: the contract keeps bad rows OUT of bronze, so the gate never sees bad values -"
say "     what it catches is a VOLUME shortfall. That is the Day-4 volume pillar."
say "Then show run 'final_green_run': all 13 tasks green."
pause

# --- 6 ---------------------------------------------------------------
banner "The copilot answers with citations" \
        "Deliverable 3. Three questions, three different behaviours."
PYTHONPATH=. PYTHONUNBUFFERED=1 $PY -c "
from src.rag.pipeline import ask
qs = [('Correct answer, with citations',
       'MATAF_01 has been above 90% for 12 minutes. Who authorizes diversion?'),
      ('Arabic question, Arabic answer',
       'ما هي إجراءات الإخلاء؟'),
      ('Refuses when the procedures do not cover it',
       'What is the refund policy for a cancelled Umrah booking?')]
for label, q in qs:
    a = ask(q)
    print('   ' + '-'*64)
    print(f'   [{label}]')
    print(f'   Q: {q}')
    print(f'   A: {a.answer[:340]}')
    print(f'      cited: {sorted({c.doc_code for c in a.citations})}')
    print()
" 2>/dev/null | grep -viE "batches|it/s|loading"
say "Say: refusing is the most important behaviour - an invented policy is worse than useless"
pause

# --- 7 ---------------------------------------------------------------
banner "Hybrid search and RRF" \
        "Deliverable 3. Two retrievers, fused by a formula written by hand."
echo "   ${BOLD}score(d)  =  SUM  1 / (k + rank of d in list i),   k = 60${OFF}"
echo
say "It fuses RANKS, not scores: 0.83 and 14.2 are not comparable, but 1st and 3rd are."
echo
echo "   Open: docs/evidence/rag/hybrid_proof.md"
echo "   ${DIM}It reports a result that did NOT match the textbook expectation, and why.${OFF}"
pause

# --- 8 ---------------------------------------------------------------
banner "Lineage, tests, and the final check" \
        "Deliverable 5, plus proof that every requirement is met."
PYTHONPATH=. PYTHONUNBUFFERED=1 $PY -c "
import json, collections
for name, path in [('healthy run   ', 'docs/evidence/lineage/events.jsonl'),
                   ('gate-failure  ', 'docs/evidence/lineage/events_gate2_failure.jsonl')]:
    c = collections.Counter()
    for line in open(path):
        c[json.loads(line)['eventType']] += 1
    print(f'   {name}: ' + '   '.join(f'{k} {v}' for k, v in sorted(c.items())))
"
echo
$PY -m pytest tests/ -q 2>/dev/null | tail -1 | sed 's/^/   /'
echo
PYTHONPATH=. $PY scripts/rubric_selfcheck.py 2>/dev/null | tail -3 | sed 's/^/   /'
echo
echo "${BOLD}${GREEN}  Demo complete.${OFF}"
echo "${DIM}  Everything shown is committed under docs/evidence/ if you need to show it again.${OFF}"
echo
