# Contributing to Nimbus

## Summary

Nimbus is a small retrieval-augmented study assistant and a runnable workshop
about LLM benchmarking, production infrastructure, and diagnosis-first scaling.
It is intentionally compact enough to read end-to-end. The project demonstrates
how latency, cost, quality, caching, routing, concurrency, and load shedding
interact in a real request path.

The primary codebase is this `adsc-workshop/` repository. The parent `ADSC/`
directory contains presentation and activity-planning material. The unrelated
`demo-repository/` directory is not part of Nimbus.

The main engineering principle is:

```text
measure → identify the bottleneck → change one lever → measure again
```

Nimbus is designed to make that loop observable. In particular, it reports
queue wait and compute time separately, because an overloaded queue and a slow
model require different fixes.

The project has two supported runtime modes:

- **Local mode:** FastAPI, local retrieval, and two CPU Hugging Face model tiers.
- **Cloud mode:** FastAPI and local retrieval running on Cloud Run, with
  generation delegated to a Google-managed model through ADC.

The participant-facing service is deliberately small. It is suitable for the
workshop and experimentation, but it is not a complete production platform:
state is in memory, observability is lightweight, and the public deployment
requires additional abuse protection for any long-lived or untrusted use.

## Setup

All commands in this document run from the `adsc-workshop/` directory.

### Prerequisites

For local development:

- Python 3.10 or newer;
- two terminal tabs for the service and benchmark;
- approximately 3 GB of disk space for packages and model weights;
- network access during initial setup only.

For Cloud Run deployment:

- Google Cloud project with billing enabled;
- Cloud Run, Cloud Build, Artifact Registry, Vertex AI, and Secret Manager APIs;
- a runtime service account with Vertex AI access and access to the admin-token
  secret;
- `gcloud` and Git;
- model access enabled in the selected Google Cloud region.

Never commit API keys, service-account JSON files, admin tokens, populated
deployment environment files, local model weights, the retrieval index, or
benchmark output.

### Local setup

Create the virtual environment, install the pinned dependencies, build the
retrieval index, and prefetch the local model weights:

```bash
make setup
```

`make setup` installs from [`requirements.txt`](requirements.txt), builds
`data/index.npz` from the course notes, and runs the model prefetch step. The
service normally runs offline after this setup and does not download weights on
request.

Start the service:

```bash
make serve
```

The default URL is `http://127.0.0.1:8000`. To use another port:

```bash
make serve PORT=8001
```

In another terminal, verify readiness and try the participant API:

```bash
curl -fsS http://127.0.0.1:8000/health

curl -N -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is overfitting?"}'
```

The `/ask` response is Server-Sent Events. It emits answer deltas, one final
`stats` event, and a `[DONE]` marker.

### Local development loop

For the optimization activity, edit only
[`01_deploy/config.py`](01_deploy/config.py), change one setting, then reload
and benchmark:

```bash
make reload
make bench ARGS="--label 'describe the change'"
```

`make reload` re-reads the configuration without reloading the local models and
clears answer caches so the next measurement starts fairly. Restart the service
if the backend, model-loading behavior, or imported Python code changes.

Useful commands:

```bash
make metrics                 # inspect the running configuration and counters
make bench                   # run the default load benchmark
make bench ARGS="--requests 32 --concurrency 16"
make reset-config            # restore the shipped workshop defaults
make clean                   # remove ignored benchmark result JSON files
```

### Tests and checks

Run the contributor checks before opening a change:

```bash
make setup
.venv/bin/python -m unittest discover -s tests -v
python3 -m compileall -q 01_deploy 02_benchmark facilitators data
git diff --check
bash -n deploy/deploy.sh
```

The tests do not require Google credentials or a live provider. The cloud-model
tests use `httpx.MockTransport` to verify response parsing and retry behavior;
the benchmark test verifies that an in-stream error is not counted as success.

For changes affecting local generation, retrieval, prompt construction, cache
behavior, or measured artifacts, also run an actual service smoke test and
recalibrate the relevant facilitator artifacts.

### Cloud Run setup

Copy the deployment template into an ignored file and fill in the cloud-owned
values:

```bash
cp deploy/cloudrun.env.example deploy/cloudrun.env
source deploy/cloudrun.env
bash deploy/deploy.sh
```

The deployment creates or reuses an Artifact Registry repository, builds the
image with Cloud Build, deploys one Cloud Run service, injects the admin token
from Secret Manager, and prints the service URL.

Verify the deployed service:

```bash
export NIMBUS_URL='https://your-service-xxxxx.run.app'
export NIMBUS_ADMIN_TOKEN='value-from-secret-manager'

curl -fsS "$NIMBUS_URL/health"
make metrics URL="$NIMBUS_URL"
make bench URL="$NIMBUS_URL"
```

The participant page and `/ask` endpoint are public by design. `/metrics` and
`/reload` require `X-Nimbus-Admin-Token`. Do not put the admin token in browser
code or send it with participant requests.

## Details and architecture

### Repository map

```text
01_deploy/
  app.py             FastAPI app, endpoints, admission, streaming, timing
  config.py          workshop levers and runtime environment overrides
  levers.py          prompt construction, caches, and model routing
  retrieval.py       brute-force search over the local embedding index
  model.py           local SmolLM generation adapter
  cloud_model.py     Google-managed model adapter
  timing.py          queue-wait and compute stopwatch
  web/index.html     participant browser UI

data/
  course_notes/      source Markdown knowledge base
  build_index.py     build-time chunking and embedding
  index.npz          generated retrieval artifact; ignored by Git

02_benchmark/
  run.py             deterministic Poisson load generator
  report.py          percentiles, token pricing, and PASS/FAIL verdict
  prompts.jsonl      frozen benchmark corpus with deliberate repeats
  decision_sheet.md  participant worksheet
  eval_card.md       measured quality summary

facilitators/
  calibrate.py       measure the optimization ladder
  eval.py            keyword-groundedness quality proxy
  eval_all.py        evaluate multiple configurations
  defaults.py        canonical shipped configuration
  gen_prompts.py     regenerate the benchmark corpus
  make_*.py          regenerate measured facilitator documents

deploy/
  deploy.sh          Cloud Run build and deployment workflow
  cloudrun.env.example
                     deployment configuration template

Dockerfile           cloud image definition
Makefile             common setup, serve, benchmark, and admin commands
scenario.json        locked workshop constraints and pricing assumptions
```

### End-to-end request flow

The core path is implemented in [`01_deploy/app.py`](01_deploy/app.py):

```text
HTTP request
    ↓
load-shedding check
    ↓
in-process semaphore
    ↓
semantic-cache lookup
    ↓ miss
embedding retrieval
    ↓
static prompt + course notes + question
    ↓
exact response-cache lookup
    ↓ miss
model tier selection
    ↓
streamed generation
    ↓
cache population
    ↓
stats event + [DONE]
```

1. FastAPI validates `question` and the optional request-level `max_tokens`
   override with Pydantic.
2. The service checks `SHED_ABOVE_QUEUE`. If the queue is too deep, it returns
   `429` with `Retry-After: 2` and the current queue depth.
3. The request waits on a semaphore sized as
   `MAX_CONCURRENT * REPLICAS`. The local `REPLICAS` setting is a simulation;
   Cloud Run instance count is configured by the deployment platform.
4. Semantic caching is checked first because a hit can bypass retrieval and
   generation.
5. On a semantic miss, the question is embedded and compared with the
   precomputed note vectors. The top `RETRIEVE_K` chunks are inserted into the
   prompt.
6. The exact response cache is checked using a hash of the assembled prompt.
7. On a cache miss, `pick_tier()` selects `small` or `large`, then the selected
   adapter streams generated text.
8. The completed answer is stored in enabled caches. Successful requests emit
   queue time, compute time, stage timings, token counts, cache state, provider,
   model, and tier.
9. The semaphore is released in `finally`, including request failures and
   cancellations.

If generation fails after the HTTP stream has begun, the service cannot change
the status code. It emits a machine-readable error event inside the stream and
then `[DONE]`; the browser and benchmark explicitly detect this condition.

### Timing model

[`timing.py`](01_deploy/timing.py) records:

- **queue wait:** request arrival until semaphore admission;
- **compute:** semaphore admission until final accounting;
- **stage timings:** cache, retrieval, prompt assembly, and generation.

This distinction is the main diagnostic signal. High queue wait points toward
efficiency, concurrency, scaling, or load management. High compute points toward
prompt size, retrieval size, output length, model choice, or model execution.

### Retrieval and prompt construction

[`data/build_index.py`](data/build_index.py) turns each `##` Markdown section
into a note chunk and embeds it with
`sentence-transformers/all-MiniLM-L6-v2`. Vectors are L2-normalized, making
cosine similarity a NumPy dot product.

The index is intentionally small and loaded locally. There is no vector
database, network retrieval service, or request-time index construction.

[`levers.py`](01_deploy/levers.py) constructs prompts in this order:

```text
system instructions
course notes
student question
answer marker
```

The static portion must remain first. Local prefix caching can only reuse tokens
up to the first changing part of the prompt.

### Cache behavior

Nimbus contains three intentionally different caches:

| Cache | Key or match | What it skips | Cost behavior |
|---|---|---|---|
| Response | SHA-256 of assembled prompt | Retrieval and generation | No model cost |
| Semantic | Embedding similarity above threshold | Retrieval and generation | No model cost, but quality risk |
| Prefix | Static prompt prefix and model tier | Local prompt prefill | Generation still runs; input is discounted in the model |

All caches are process-local. `/reload` clears exact and semantic answer caches.
Prefix seeds are keyed by a prefix hash and are not cleared by
`reset_caches()`.

### Model adapters

Both adapters expose the same conceptual contract:

```text
warm()
generate(tier, prompt, max_tokens, stats, prefix_text)
close()                 # optional
runtime_info()          # optional
```

The local adapter loads both SmolLM tiers once and uses Hugging Face streaming
generation in worker threads so blocking iterator calls do not stall the
asyncio event loop.

The cloud adapter uses Google ADC, not API keys or checked-in service-account
files. It supports the configured managed endpoint, parses SSE/NDJSON/JSON
responses, records provider token usage when available, and retries transient
provider/network failures before any text has been emitted.

The cloud deployment defaults both tier IDs to the same managed model unless
separate model settings are supplied. Therefore `ROUTE_EASY` has a meaningful
local effect by default, but may not change cloud inference cost or capability
without distinct cloud model IDs.

### Configuration and reload behavior

[`config.py`](01_deploy/config.py) is the single workshop control panel. Its
source values define the local exercise; `NIMBUS_*` environment variables are
applied afterward for Cloud Run.

The optimization ladder is:

1. confirm queue versus compute;
2. enable response, prefix, and semantic caching;
3. reduce system prompt, retrieved chunks, and output tokens;
4. route easy requests to the small model;
5. add concurrency or replicas;
6. shed excess load honestly.

`/reload` reloads `config.py`, clears answer caches, replaces the semaphore, and
resets counters. It is intended for configuration levers. Changing the selected
backend or other process-level provider state requires a restart.

### Public API and participant UI

The browser UI in [`01_deploy/web/index.html`](01_deploy/web/index.html) is a
minimal same-origin client. It sends a question to `/ask`, parses SSE events,
renders deltas as they arrive, and surfaces service errors and provider usage
availability.

There is no separate frontend server or API gateway. FastAPI serves the static
page and is itself the backend proxy that protects model credentials, performs
retrieval, controls concurrency, and streams the answer.

### Benchmark and cost model

[`02_benchmark/run.py`](02_benchmark/run.py) uses a deterministic 60-row corpus
with exact repeats, semantic near-repeats, and a long tail. The default run uses
16 requests, a 4 request/second Poisson arrival rate, concurrency 8, and two
warm-up requests.

The benchmark records TTFT from the first streamed delta and end-to-end latency
from request send until stream completion. It separately records server-side
queue wait and compute values.

[`report.py`](02_benchmark/report.py) prices successful non-cache requests from
`scenario.json`. Prefix-cached input tokens use the configured discounted input
rate. Cloud provider usage that is not reported produces an `UNKNOWN` cost
verdict rather than silently treating the request as free.

The benchmark verdict checks latency and budget. Quality is a separate concern
evaluated by the facilitator harness and the generated eval card.

### Quality evaluation

[`facilitators/eval.py`](facilitators/eval.py) runs 36 known-answer questions:

- extraction cases, where the fact appears directly in a retrieved note;
- reasoning cases, where the answer requires combining or applying facts.

The evaluator is a keyword-groundedness proxy. It does not reliably measure
fluency, tone, completeness, safety, or subtle correctness. Treat it as a
workshop signal, not a production quality gate.

When changing prompts, retrieval, model tiers, benchmark questions, or serving
behavior, regenerate measured artifacts using the facilitator workflow:

```bash
make serve
.venv/bin/python facilitators/calibrate.py
.venv/bin/python facilitators/eval_all.py
.venv/bin/python facilitators/make_answer_key.py
.venv/bin/python facilitators/make_eval_card.py
```

Calibration must run alone on the machine. Latency is hardware-dependent;
token-derived cost is more portable. Always restore shipped defaults before
committing or running a participant session.

### Cloud image and deployment architecture

The [`Dockerfile`](Dockerfile) installs the pinned runtime dependencies, copies
the source, and builds the retrieval index during image construction. It does
not package the local generation model weights.

At runtime the image:

- runs as a non-root `nimbus` user;
- listens on Cloud Run’s `PORT` (8080 by default);
- uses `NIMBUS_MODEL_BACKEND=google`;
- serves local retrieval and prompt/caching logic;
- calls the managed Google model endpoint for generation.

The default deployment is one 1-vCPU/1-GiB instance, Cloud Run concurrency 2,
and maximum instances 1. These are workshop starting points, not permanent
capacity recommendations.

### Important invariants

These conditions affect whether the exercise and its measurements remain valid:

- Keep service `MAX_CONCURRENT` below benchmark concurrency, otherwise queue
  wait disappears and the bottleneck diagnosis is invalid.
- Preserve the repeating structure of `prompts.jsonl`; duplicates must exist in
  the first benchmark prefix so cache effects are measurable.
- Keep static prompt content before the changing question for prefix caching.
- Load models before serving traffic; never load model weights in a request
  handler.
- Run calibration without unrelated CPU-heavy work.
- Treat the default 16-request p95/p99 values as coarse; use more requests for
  close decisions.
- Never interpret a quality score from extraction-only questions as sufficient.
- Keep `scenario.json` and generated facilitator documents synchronized.

### Current production-readiness boundaries

Before using this design beyond a controlled workshop, add or evaluate:

- shared or externalized cache and metrics state across Cloud Run instances;
- bounded cache size, TTLs, invalidation, and tenant isolation;
- a hard server-side maximum for request-level token overrides;
- edge rate limiting, abuse protection, and request quotas;
- structured logs, traces, provider dashboards, and durable metrics;
- stronger quality, safety, prompt-injection, and regression evaluations;
- deployment smoke tests and a real Cloud Run integration test;
- a strategy for backend/model changes that invalidates process-local state.

Keep changes focused, explain cross-area dependencies in the commit message, and
do not mix generated benchmark outputs or secrets with source changes.
