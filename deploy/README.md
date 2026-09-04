# Nimbus on Cloud Run

Nimbus already contains the backend proxy needed for the cloud deployment:

```text
participant browser -> Cloud Run FastAPI -> retrieval/cache/queue
                    -> Google managed model API -> streamed answer
```

There is no second proxy to deploy. Keeping the proxy in this repository is
important because it protects the model credential, performs course-note
retrieval, controls concurrency, exposes timing data, and gives the workshop a
single place to enforce request limits.

## What the cloud owner must provide

1. A Google Cloud project with billing enabled and a budget alert.
2. APIs enabled for Cloud Run, Cloud Build, Artifact Registry, Vertex AI, and
   Secret Manager.
3. A user-managed runtime service account. Grant it:
   - `roles/aiplatform.user` on the project;
   - `roles/secretmanager.secretAccessor` on the `nimbus-admin-token` secret.
4. Mistral model access enabled in Model Garden, in the same region used by
   Cloud Run. The default `mistral-small-2503` is currently listed for
   `us-central1` and `europe-west4`.
5. A Secret Manager secret containing a random admin token. It protects
   `/metrics` and `/reload`; it is not used by participants.
6. A deployer identity with Cloud Run deploy, Artifact Registry write/build,
   service-account-use, and the required Cloud Build permissions.
7. **Build permissions for the Cloud Build runner.** Projects created from
   about 2024 onward no longer grant the Compute Engine default service
   account any roles, and Cloud Build runs as that account by default. Without
   the grant below `gcloud builds submit` fails at the *first* step, before any
   build output, with:

   ```text
   ERROR: could not resolve source: ... does not have storage.objects.get
   access to the Google Cloud Storage object
   ```

   Least-privilege fix — three roles, nothing that can deploy or read secrets:

   ```bash
   SA="$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" \
        --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
   for role in roles/logging.logWriter \
               roles/artifactregistry.writer \
               roles/storage.objectViewer; do
     gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
       --member="serviceAccount:${SA}" --role="$role" --condition=None
   done
   ```

   `roles/cloudbuild.builds.builder` is the commonly documented single-role
   alternative; it also works and grants rather more.

No service-account JSON key, API key, or admin token should be added to this
repository. Cloud Run uses Application Default Credentials from its runtime
service account.

## Deploy

Copy the example variables into a local, ignored env file, fill in the project
and service-account values, then run:

```bash
cp deploy/cloudrun.env.example deploy/cloudrun.env
source deploy/cloudrun.env
bash deploy/deploy.sh
```

The script builds the image with Cloud Build, creates the Artifact Registry
repository if necessary, deploys one Cloud Run service, and prints its URL.
The image builds the small local embedding/index artifact; LLM inference stays
on the managed Google endpoint, so the Cloud Run instance does not need a GPU.

The default shape is one 1-vCPU/1-GiB instance with concurrency 2 and max
instances 1. This is a starting point for 10–20 participants, not a permanent
capacity claim. Increase `NIMBUS_MAX_INSTANCES` only after measuring queue wait
and checking the budget. Set `NIMBUS_MIN_INSTANCES=0` outside the live session
to reduce idle cost.

The service is intentionally public so participants can use a browser without
Google accounts. Keep this deployment limited to the workshop, retain the
budget alert, and put Cloud Armor or an identity-aware access layer in front of
it before using the same pattern for an untrusted or long-lived application.

## Verify

```bash
export NIMBUS_URL='https://...run.app'
export NIMBUS_ADMIN_TOKEN='the-value-from-secret-manager'
curl -fsS "$NIMBUS_URL/health"
make metrics
make bench URL="$NIMBUS_URL"
```

The benchmark never writes `NIMBUS_ADMIN_TOKEN` to its result JSON. If the
managed provider does not include usage in a streaming response, the report
marks the cost verdict as unknown instead of treating zero tokens as free.

## Model choice

**Verify the model with a real request before the session.** `warm()` validates
credentials, not model access, so a service configured with a model the project
cannot reach starts up *healthy* and then fails every `/ask` with a 404. On
`adsc-nimbus`, `mistral-small-2503` is exactly this case: it returns 404 in both
`us-central1` and `global` because Model Garden access was never granted.

The workshop therefore runs on Gemini, with two real tiers:

| Setting | Value |
| --- | --- |
| `NIMBUS_GOOGLE_API_STYLE` | `gemini` |
| `NIMBUS_GOOGLE_MODEL_SMALL` | `gemini-2.5-flash-lite` |
| `NIMBUS_GOOGLE_MODEL_LARGE` | `gemini-2.5-flash` |
| `NIMBUS_GEMINI_THINKING_BUDGET` | `0` |

Leave `NIMBUS_GOOGLE_MODEL_ID` **unset**. It pins both tiers to a single model,
which silently removes routing as a lever.

`NIMBUS_GEMINI_THINKING_BUDGET=0` is not a tuning preference. Gemini 2.5 spends
the *output* token budget thinking before it answers, so at the workshop default
of `MAX_TOKENS=32` the model returns `finishReason=MAX_TOKENS` with **no text at
all** and `thoughtsTokenCount=29` — every answer empty, while latency and cost
still read as perfectly healthy. Use `none` to omit the field entirely, which
`gemini-2.5-pro` requires because it refuses a zero budget.

The `decode` incident intentionally overrides the large tier to
`gemini-2.5-pro`, uses its minimum explicit thinking budget of `128`, and
selects the `VERBOSE` system prompt so output work is measurably the
bottleneck. Pro cannot disable thinking; if it receives the old zero-budget
default, the adapter omits that field and lets Pro use automatic thinking.



The adapter defaults to Google’s managed `mistral-small-2503` endpoint in
`us-central1`, and the model ID is configurable. The current Google pricing
page lists Mistral Small 3.1 at $0.10 per 1M input tokens and $0.30 per 1M
output tokens; `scenario.json` contains those rates as an auditable workshop
assumption. Verify availability and pricing with the cloud owner immediately
before the event. Do not hard-code a retiring model as the only fallback;
changing `NIMBUS_GOOGLE_MODEL_ID` should not require a source or credential
change.

The default `mistral` API style calls the publisher `streamRawPredict` endpoint
with the Mistral model ID. The optional `openai` style is for a compatible
OpenAI endpoint and requires an explicit `NIMBUS_GOOGLE_MODEL_ID` (for example,
the provider-qualified model ID documented by Google); it is not the default
path for managed Mistral.
