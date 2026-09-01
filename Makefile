VENV := .venv
PY   := $(VENV)/bin/python
PORT ?= 8000
URL  ?= http://127.0.0.1:$(PORT)

setup:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt
	NIMBUS_ALLOW_MODEL_DOWNLOAD=1 $(PY) data/build_index.py
	$(PY) .devcontainer/prefetch.py

serve:
	$(VENV)/bin/uvicorn app:app --app-dir 01_deploy --host 0.0.0.0 --port $(PORT)

public:
	gh codespace ports visibility $(PORT):public

bench:
	$(PY) 02_benchmark/run.py --url $(URL) $(ARGS)

reload:
	@curl -s -X POST $(URL)/reload | $(PY) -m json.tool

metrics:
	@curl -s $(URL)/metrics | $(PY) -m json.tool

reset-config:
	@$(PY) facilitators/defaults.py

clean:
	rm -rf results/*.json

.PHONY: setup serve public bench reload metrics reset-config clean
