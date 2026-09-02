"""Google managed-model adapter used by the Cloud Run deployment.

The FastAPI application deliberately keeps the same ``warm``/``generate``
contract as the local model implementation.  That lets the workshop keep a
local fallback while Cloud Run sends inference to a managed Google endpoint.

Authentication uses Application Default Credentials, which means a Cloud Run
runtime service account is used in production.  No service-account key or API
key belongs in the container or repository.
"""
import asyncio
import json
import os
from typing import AsyncIterator

import httpx


class ProviderError(RuntimeError):
    """An upstream model request failed before a response could complete."""


class RetryableProviderError(ProviderError):
    """The upstream response may succeed if retried with backoff."""


_credentials = None
_project = None
_http: httpx.AsyncClient | None = None
_refresh_lock: asyncio.Lock | None = None


def _api_style() -> str:
    return os.environ.get("NIMBUS_GOOGLE_API_STYLE", "mistral").lower()


def _model_id(tier: str) -> str:
    common = os.environ.get("NIMBUS_GOOGLE_MODEL_ID")
    if common:
        return common
    if tier == "small":
        return os.environ.get("NIMBUS_GOOGLE_MODEL_SMALL", "mistral-small-2503")
    return os.environ.get("NIMBUS_GOOGLE_MODEL_LARGE", "mistral-small-2503")


def _load_credentials() -> None:
    global _credentials, _project
    if _credentials is not None:
        return

    try:
        import google.auth
        from google.auth.transport.requests import Request

        _credentials, discovered_project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"])
        _project = os.environ.get("GOOGLE_CLOUD_PROJECT") or discovered_project
        if not _project:
            raise RuntimeError("GOOGLE_CLOUD_PROJECT is not set and ADC returned no project")
        _credentials.refresh(Request())
    except Exception as exc:  # noqa: BLE001
        raise ProviderError(
            "Google credentials are unavailable. Configure Cloud Run ADC or run "
            "`gcloud auth application-default login` locally.") from exc


async def _access_token() -> str:
    global _refresh_lock
    if _credentials is None:
        await asyncio.to_thread(_load_credentials)

    if _refresh_lock is None:
        _refresh_lock = asyncio.Lock()
    if not _credentials.valid or _credentials.expired:
        async with _refresh_lock:
            if not _credentials.valid or _credentials.expired:
                from google.auth.transport.requests import Request
                await asyncio.to_thread(_credentials.refresh, Request())
    if not _credentials.token:
        raise ProviderError("Google credentials did not return an access token")
    return _credentials.token


def _endpoint(model_id: str) -> str:
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    project = _project or os.environ.get("GOOGLE_CLOUD_PROJECT")
    host = f"{location}-aiplatform.googleapis.com"
    if _api_style() == "mistral":
        return (f"https://{host}/v1/projects/{project}/locations/{location}/"
                f"publishers/mistralai/models/{model_id}:streamRawPredict")
    return (f"https://{host}/v1/projects/{project}/locations/{location}/"
            "endpoints/openapi/chat/completions")


def runtime_info() -> dict:
    """Return non-secret provider details for /metrics and benchmark records."""
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    return {
        "provider": "google",
        "api_style": _api_style(),
        "location": location,
        "model_small": _model_id("small"),
        "model_large": _model_id("large"),
    }


def _http_client() -> httpx.AsyncClient:
    global _http
    if _http is None:
        timeout = float(os.environ.get("NIMBUS_PROVIDER_TIMEOUT_SECONDS", "300"))
        _http = httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=15.0))
    return _http


def _usage(stats: dict, payload: dict) -> None:
    usage = payload.get("usage") or {}
    if not usage:
        return

    stats["tokens_in"] = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
    stats["tokens_out"] = int(
        usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0)
    details = usage.get("prompt_tokens_details") or usage.get("input_tokens_details") or {}
    stats["tokens_cached"] = int(
        usage.get("cached_tokens", details.get("cached_tokens", 0)) or 0)
    stats["usage_source"] = "provider"


async def _stream_once(model_id: str, prompt: str, max_tokens: int,
                       stats: dict) -> AsyncIterator[str]:
    token = await _access_token()
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "stream": True,
    }
    async with _http_client().stream(
            "POST", _endpoint(model_id),
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            json=payload) as response:
        if response.status_code == 429 or response.status_code >= 500:
            detail = (await response.aread()).decode(errors="replace")[:500]
            raise RetryableProviderError(
                f"Google model returned HTTP {response.status_code}: {detail}")
        if response.status_code >= 400:
            detail = (await response.aread()).decode(errors="replace")[:500]
            raise ProviderError(
                f"Google model returned HTTP {response.status_code}: {detail}")

        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            raw = line[6:]
            if raw == "[DONE]":
                break
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            _usage(stats, event)
            for choice in event.get("choices", []):
                text = (choice.get("delta") or {}).get("content") or ""
                if text:
                    yield text


def warm() -> None:
    """Validate Google ADC during startup, before Cloud Run accepts traffic."""
    if _api_style() not in {"mistral", "openai"}:
        raise ProviderError("NIMBUS_GOOGLE_API_STYLE must be 'mistral' or 'openai'")
    _load_credentials()


async def close() -> None:
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None


async def generate(tier: str, prompt: str, max_tokens: int, stats: dict,
                   prefix_text: str | None = None):
    """Stream text from the configured Google managed model.

    ``prefix_text`` is accepted for compatibility with the local backend.  A
    managed provider owns its KV/prompt cache, so the application does not pass
    a local cache object to it.
    """
    model_id = _model_id(tier)
    stats.update({"provider": "google", "model": model_id,
                  "usage_source": "unreported", "tokens_in": 0,
                  "tokens_out": 0, "tokens_cached": 0})
    retries = max(0, int(os.environ.get("NIMBUS_PROVIDER_RETRIES", "2")))
    backoff = float(os.environ.get("NIMBUS_PROVIDER_BACKOFF_SECONDS", "0.5"))

    for attempt in range(retries + 1):
        yielded = False
        try:
            async for text in _stream_once(model_id, prompt, max_tokens, stats):
                yielded = True
                yield text
            return
        except RetryableProviderError:
            if yielded or attempt >= retries:
                raise
            await asyncio.sleep(backoff * (2 ** attempt))
