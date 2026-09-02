VENV := .venv
PY   := $(VENV)/bin/python
PORT ?= 8000
URL  ?= $(if $(NIMBUS_URL),$(NIMBUS_URL),http://127.0.0.1:$(PORT))
NIMBUS_PORT ?= 8000
COMPOSE ?= docker compose -f docker-compose.local.yml

setup:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt
	NIMBUS_ALLOW_MODEL_DOWNLOAD=1 $(PY) data/build_index.py
	$(PY) .devcontainer/prefetch.py

serve:
	$(VENV)/bin/uvicorn app:app --app-dir 01_deploy --host 0.0.0.0 --port $(PORT)

# Local-first Docker path: Ollama, the Nimbus proxy, retrieval, and the
# benchmark all run without Google credentials. Model weights persist in the
# named ollama-models volume across app rebuilds.
docker-up:
	$(COMPOSE) up -d --build --wait

docker-down:
	$(COMPOSE) down

docker-logs:
	$(COMPOSE) logs -f nimbus

docker-bench:
	$(COMPOSE) exec -T nimbus python 02_benchmark/run.py --url http://127.0.0.1:8000 $(ARGS)

docker-reload:
	@curl -fsS -X POST http://127.0.0.1:$(NIMBUS_PORT)/reload

docker-metrics:
	@curl -fsS http://127.0.0.1:$(NIMBUS_PORT)/metrics

public:
	gh codespace ports visibility $(PORT):public

bench:
	$(PY) 02_benchmark/run.py --url $(URL) $(ARGS)

reload:
	@curl -sS -X POST $(URL)/reload \
		-H "X-Nimbus-Admin-Token: $${NIMBUS_ADMIN_TOKEN}" | $(PY) -m json.tool

metrics:
	@curl -sS $(URL)/metrics \
		-H "X-Nimbus-Admin-Token: $${NIMBUS_ADMIN_TOKEN}" | $(PY) -m json.tool

reset-config:
	@$(PY) facilitators/defaults.py

clean:
	rm -rf results/*.json

.PHONY: setup serve docker-up docker-down docker-logs docker-bench docker-reload docker-metrics public bench reload metrics reset-config clean
