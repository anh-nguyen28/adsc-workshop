# Nimbus participant preflight

Do this **before** the workshop. It prevents model downloads and environment
setup from taking time away from the hands-on incident.

## What you need

- Docker Desktop or Docker Engine with Compose v2.
- At least 8 GB of RAM recommended for the default Llama 3.1 8B model.
- About 8 GB of free disk space for the app image, embedding model, and Llama
  weights.
- Two terminal tabs and a code editor.

## Local Docker setup

From the `adsc-workshop` folder, run:

```bash
make docker-up
```

The first command builds the app and downloads `llama3.1:8b` once into the
persistent `ollama-models` volume. It can take several minutes. Verify it with:

```bash
curl -fsS http://127.0.0.1:8000/health
make docker-bench ARGS="--requests 4 --concurrency 1"
```

Nimbus then serves strictly from the local Ollama/model and retrieval caches;
it will not use Google or another hosted model during the activity.

When you are done, run `make docker-down`. Keep the volume if you want to avoid
downloading the model again.

## Python-local setup (optional lightweight path)

If Docker is unavailable, the original Python setup remains supported:

```bash
make setup
.venv/bin/python .devcontainer/prefetch.py
```

Then verify the service can start:

```bash
make serve
```

When you see `Nimbus ready`, stop it with `Ctrl-C`. You are ready. During the
workshop you will start it again, benchmark it, and edit only
`01_deploy/config.py`.

## Cloud Run participant path

If the facilitator deploys the cloud version, participants need only the shared
Cloud Run URL and a browser. Open the URL, ask questions in the Nimbus page,
and do not copy an admin token into the browser. Facilitators keep that token
for `/metrics`, `/reload`, and remote benchmarking.

## Codespaces setup

Open the repository in a Codespace at least once before the session. Wait for
the post-create setup to finish and for the terminal to print `Nimbus workshop
ready.` Then run `make serve` once and stop it after `Nimbus ready` appears.

## If setup fails

Do not spend workshop time debugging package installation. Join a teammate or
use the paper track; it teaches the same decision process. Tell a facilitator
which command and error you saw.
