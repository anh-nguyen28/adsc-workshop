# Nimbus Workshop

Nimbus is a small retrieval-augmented study assistant used for a hands-on
exercise about latency, cost, quality, and capacity. The application can run
locally for the optimization activity or on Cloud Run so participants only
need a browser.

## Choose a path

| Who | Start here | What you need |
| --- | --- | --- |
| Participant using the shared cloud service | Open the URL from the facilitator | A browser |
| Facilitator deploying the shared service | [`deploy/README.md`](deploy/README.md) | Google Cloud project and permissions |
| Facilitator benchmarking Cloud Run | [`02_benchmark/README.md`](02_benchmark/README.md) | A prepared checkout and admin token |
| Participant or facilitator running locally | [`participant-preflight.md`](participant-preflight.md) | Python 3.10+ and about 3 GB disk |

The detailed local service guide is [`01_deploy/README.md`](01_deploy/README.md).

## What the workshop teaches

You will diagnose a slow service, change one lever at a time, and prove the
effect with measurements. The important distinction is:

- High queue wait means requests are waiting for capacity.
- High compute time means each request is doing too much work.
- High quality with unacceptable cost requires a trade-off, not a guess.

The optimization ladder is deliberately ordered:

1. Measure the baseline.
2. Enable useful response or semantic caching.
3. Reduce prompt, retrieval, and output work.
4. Route easy questions to a cheaper model when a second model is configured.
5. Add concurrency or Cloud Run instances only after measuring the queue.
6. Shed excess load honestly when serving everyone would cause timeouts.

## Architecture

```text
participant browser
        │
        ▼
Cloud Run or local FastAPI service  (the backend proxy)
        │  retrieval · cache · queue · timing · SSE
        ▼
Google-managed model API             or local Hugging Face models
```

The FastAPI service is already the proxy. It keeps model credentials out of
the browser, retrieves course notes, controls concurrency, records metrics, and
streams answers. A second API gateway or backend proxy is not required for a
10–20 participant workshop.

## Cloud Run quick start

### For participants

Open the Cloud Run URL in a browser and ask questions from the Nimbus page.
Participants do not need to clone the repository and should never receive the
admin token.

### For the facilitator

The default deployment uses one 1-vCPU/1-GiB Cloud Run instance, concurrency 2,
and maximum instances 1. This is a starting point for 10–20 participants;
measure queue wait before increasing capacity.

1. Ask the cloud owner for the project ID, region, runtime service account,
   model access, and `nimbus-admin-token` Secret Manager secret.
2. Copy and fill the deployment variables:

   ```bash
   cp deploy/cloudrun.env.example deploy/cloudrun.env
   # edit deploy/cloudrun.env; do not commit it
   source deploy/cloudrun.env
   ```

3. Build and deploy:

   ```bash
   bash deploy/deploy.sh
   ```

4. Save the printed service URL and verify it:

   ```bash
   export NIMBUS_URL='https://your-service-xxxxx.run.app'
   export NIMBUS_ADMIN_TOKEN='value-from-secret-manager'
   curl -fsS "$NIMBUS_URL/health"
   make metrics URL="$NIMBUS_URL"
   make bench URL="$NIMBUS_URL"
   ```

Cloud mode uses ADC from the Cloud Run runtime service account; no API key or
service-account JSON file belongs in this repository. The adapter defaults to
Google-managed Mistral Small 3.1 (`mistral-small-2503`), a 24B-class model, and
keeps the model ID configurable. Confirm availability and pricing before the
event in the [Google Mistral model documentation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/partner-models/mistral/mistral-small-3-1).

## Local quick start

Use this path for the original hands-on activity:

```bash
make setup       # create .venv, install dependencies, build the note index
make serve       # start the service on http://127.0.0.1:8000
```

In another terminal:

```bash
curl -N -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is Big-O notation?"}'
```

The response is Server-Sent Events. It contains answer deltas followed by a
final `stats` event and `[DONE]`.

Run the benchmark:

```bash
make bench
```

Change one setting in `01_deploy/config.py`, reload, and measure again:

```bash
make reload
make bench ARGS="--label 'trimmed prompt'"
```

For a Cloud Run benchmark, export `NIMBUS_URL` and `NIMBUS_ADMIN_TOKEN` first.
The token is used only for protected `/metrics` and `/reload`; it is not sent
to participant `/ask` requests or written to benchmark results.

## API reference

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/` | None | Participant browser UI |
| `GET` | `/health` | None | Readiness/liveness check |
| `POST` | `/ask` | None | Stream an answer as SSE |
| `GET` | `/metrics` | Admin header in cloud mode | Read config and counters |
| `POST` | `/reload` | Admin header in cloud mode | Reload local config and clear caches |

Cloud admin calls use:

```text
X-Nimbus-Admin-Token: <secret value>
```

## Configuration

Local participants edit `01_deploy/config.py`. Cloud deployments use the same
source defaults plus `NIMBUS_*` environment overrides, so the container can be
tuned without rebuilding the image. Important settings are:

| Setting | Effect |
| --- | --- |
| `RESPONSE_CACHE` | Reuses an identical completed answer |
| `SEMANTIC_CACHE` | Reuses answers for sufficiently similar questions |
| `MAX_TOKENS` | Caps generated output and model cost |
| `SYSTEM_PROMPT` | Chooses `LONG` or `TRIMMED` instructions |
| `RETRIEVE_K` | Controls how many note chunks enter the prompt |
| `MAX_CONCURRENT` | Limits in-process model work |
| `SHED_ABOVE_QUEUE` | Returns `429` when the queue is too deep |
| `NIMBUS_MAX_INSTANCES` | Cloud Run capacity, set at deployment time |

`REPLICAS` is only a local workshop simulation. Cloud Run instance count must
be configured with the deployment script and then verified with measurements.

## Repository map

```text
01_deploy/       FastAPI service, model adapters, retrieval, participant UI
02_benchmark/    Load generator and latency/cost report
facilitators/    Quality evaluation and ladder calibration tools
data/            Course notes and build-time retrieval index
deploy/          Cloud Run deployment script and cloud-owner checklist
Dockerfile       Reproducible Cloud Run image
Makefile         Setup, serve, benchmark, reload, and metrics commands
scenario.json    Workshop SLOs and model pricing inputs
```

## Troubleshooting

- `make serve` fails because the port is busy: run `make serve PORT=8001`.
- `make bench` reports zero successes: check `curl .../health`, the URL, and
  whether the service finished startup.
- Cloud `/metrics` or `/reload` returns `401`: export the correct
  `NIMBUS_ADMIN_TOKEN` in the facilitator terminal.
- Cloud startup fails: verify the runtime service account has Vertex AI access,
  the model is enabled in the selected region, and `GOOGLE_CLOUD_PROJECT` and
  `GOOGLE_CLOUD_LOCATION` are correct.
- Cost is shown as `UNKNOWN`: the streaming provider did not return token usage
  or the selected model has no price entry in `scenario.json`. Do not treat
  missing usage as zero cost.

For the full exercise instructions, use the deployment and benchmark guides
linked at the top of this page.
