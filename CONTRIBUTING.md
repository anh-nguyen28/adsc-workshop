# Working on Nimbus

This repository supports two workflows. A participant can use the shared Cloud
Run URL with only a browser. Contributors, facilitators, and cloud owners use a
prepared checkout to change, deploy, benchmark, or evaluate the service.

## Before opening a change

From the `adsc-workshop` directory:

```bash
make setup
.venv/bin/python -m unittest discover -s tests -v
python3 -m compileall -q 01_deploy 02_benchmark facilitators data
git diff --check
bash -n deploy/deploy.sh
```

`make setup` is required for the local model and retrieval index. The cloud
image builds its own retrieval index during `gcloud builds submit`; do not
commit `data/index.npz`, benchmark output, or populated deployment env files.

## Where to work

| Task | Files | Local verification |
| --- | --- | --- |
| Participant experience | `01_deploy/web/`, `01_deploy/app.py` | Start the service and open `/` |
| Local optimization activity | `01_deploy/config.py`, `01_deploy/levers.py` | `make reload`, then `make bench` |
| Google/Cloud Run integration | `01_deploy/cloud_model.py`, `Dockerfile`, `deploy/` | Contract tests and a deployed smoke request |
| Benchmarking and cost | `02_benchmark/`, `scenario.json` | `make bench` and inspect `results/` |
| Quality evaluation | `facilitators/`, `02_benchmark/eval_card.md` | Run the facilitator evaluation tools |
| Documentation/onboarding | `README.md`, `01_deploy/README.md`, `deploy/README.md` | Follow the instructions from a clean checkout |

Keep a change focused on one area when possible. If a change crosses areas,
explain the dependency in the commit body. Do not mix generated benchmark
results with source changes.

## Cloud safety

Use `deploy/cloudrun.env.example` as the starting point for deployment. A
populated `deploy/cloudrun.env` is ignored, but verify `git status` before
sharing a patch. Never add a service-account JSON key, API key, admin token, or
participant data to the repository.

Cloud owner setup and permissions are documented in [`deploy/README.md`](deploy/README.md).
The deployment script expects the Secret Manager secret and runtime service
account to exist before it runs.

## Pull request checklist

- The change has a clear scope and a useful commit message.
- Tests and static checks pass, or the PR explains the exact external blocker.
- The participant path still works without an admin token.
- `/metrics` and `/reload` remain protected in cloud mode.
- Cloud pricing or model availability claims link to the current provider
  documentation and are not treated as permanent constants.
- No secrets, generated artifacts, or local model weights are included.
