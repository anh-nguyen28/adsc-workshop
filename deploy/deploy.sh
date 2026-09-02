#!/usr/bin/env bash
set -euo pipefail

# Build and deploy Nimbus to one public Cloud Run service. The service is the
# participant-facing backend proxy: browser -> Nimbus -> managed model API.
# This script deliberately assumes the secret and runtime service account have
# already been created by the cloud owner.

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SERVICE="${NIMBUS_SERVICE:-nimbus}"
REPOSITORY="${NIMBUS_REPOSITORY:-nimbus}"
RUNTIME_SA="${NIMBUS_RUNTIME_SERVICE_ACCOUNT:?Set NIMBUS_RUNTIME_SERVICE_ACCOUNT}"
ADMIN_SECRET="${NIMBUS_ADMIN_SECRET:-nimbus-admin-token}"
MODEL_ID="${NIMBUS_GOOGLE_MODEL_ID:-mistral-small-2503}"
API_STYLE="${NIMBUS_GOOGLE_API_STYLE:-mistral}"
MIN_INSTANCES="${NIMBUS_MIN_INSTANCES:-1}"
MAX_INSTANCES="${NIMBUS_MAX_INSTANCES:-1}"
CONCURRENCY="${NIMBUS_CONCURRENCY:-2}"
APP_CONCURRENCY="${NIMBUS_MAX_CONCURRENT:-${CONCURRENCY}}"
CPU="${NIMBUS_CPU:-1}"
MEMORY="${NIMBUS_MEMORY:-1Gi}"
IMAGE_TAG="${NIMBUS_IMAGE_TAG:-$(git rev-parse --short HEAD)}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE}:${IMAGE_TAG}"

gcloud artifacts repositories describe "${REPOSITORY}" \
  --project="${PROJECT_ID}" --location="${REGION}" >/dev/null 2>&1 || \
gcloud artifacts repositories create "${REPOSITORY}" \
  --project="${PROJECT_ID}" --location="${REGION}" \
  --repository-format=docker --description="Nimbus workshop images"

gcloud builds submit . --project="${PROJECT_ID}" --tag="${IMAGE}"

gcloud run deploy "${SERVICE}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE}" \
  --service-account="${RUNTIME_SA}" \
  --port=8080 \
  --cpu="${CPU}" \
  --memory="${MEMORY}" \
  --concurrency="${CONCURRENCY}" \
  --min="${MIN_INSTANCES}" \
  --max="${MAX_INSTANCES}" \
  --timeout=3600 \
  --allow-unauthenticated \
  --set-env-vars="NIMBUS_MODEL_BACKEND=google,NIMBUS_GOOGLE_API_STYLE=${API_STYLE},NIMBUS_GOOGLE_MODEL_ID=${MODEL_ID},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},NIMBUS_RESPONSE_CACHE=${NIMBUS_RESPONSE_CACHE:-true},NIMBUS_PREFIX_CACHE=${NIMBUS_PREFIX_CACHE:-false},NIMBUS_SEMANTIC_CACHE=${NIMBUS_SEMANTIC_CACHE:-false},NIMBUS_SYSTEM_PROMPT=${NIMBUS_SYSTEM_PROMPT:-TRIMMED},NIMBUS_RETRIEVE_K=${NIMBUS_RETRIEVE_K:-3},NIMBUS_MAX_TOKENS=${NIMBUS_MAX_TOKENS:-32},NIMBUS_MAX_CONCURRENT=${APP_CONCURRENCY},NIMBUS_SHED_ABOVE_QUEUE=${NIMBUS_SHED_ABOVE_QUEUE:-4}" \
  --update-secrets="NIMBUS_ADMIN_TOKEN=${ADMIN_SECRET}:latest"

gcloud run services describe "${SERVICE}" \
  --project="${PROJECT_ID}" --region="${REGION}" \
  --format='value(status.url)'
