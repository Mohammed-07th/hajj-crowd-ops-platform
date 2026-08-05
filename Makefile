SHELL := /bin/bash
PY    := ./.venv/bin/python
AF    := ./.venv-airflow/bin/airflow

.PHONY: help up down ps topics seed reset produce ingest silver gold gate-bronze \
        pipeline airflow audit test demo-failures clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

up:              ## start kafka + qdrant
	docker compose up -d
	@echo "waiting for kafka health..."
	@until [ "$$(docker inspect --format '{{.State.Health.Status}}' hajj-kafka 2>/dev/null)" = "healthy" ]; do sleep 2; done
	./scripts/create_topics.sh

down:            ## stop containers
	docker compose down

ps:              ## show container status
	docker compose ps

topics:          ## (re)create kafka topics
	./scripts/create_topics.sh

reset:           ## drop delta tables, reset topics and lineage stream
	./scripts/reset_pipeline.sh

produce:         ## emit 200k synthetic occupancy events (7 simulated days)
	$(PY) -m src.ingestion.producers.occupancy_producer --events 200000 --corrupt-rate 0.07 --seed 42

ingest:          ## consume -> validate -> bronze delta + DLQ
	$(PY) -m src.ingestion.consumer --topic zone_occupancy_raw --idle-timeout 15

silver:          ## bronze -> silver
	$(PY) -m src.lakehouse.silver

gold:            ## silver -> gold aggregates
	$(PY) -m src.lakehouse.gold

gate-bronze:     ## run the bronze GE checkpoint (exits non-zero on failure)
	$(PY) -m src.quality.run_gate --layer bronze --min-rows 150000

pipeline: reset produce ingest gate-bronze silver gold  ## full run, no airflow

airflow:         ## start airflow webserver + scheduler on the host
	./scripts/start_airflow.sh

audit:           ## anti-substitution audit
	./scripts/verify_no_simulation.sh

test:            ## unit tests
	$(PY) -m pytest tests/ -v

clean:           ## remove generated artifacts (keeps evidence)
	rm -rf delta airflow/logs .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
