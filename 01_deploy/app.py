"""Nimbus -- the study assistant you deploy, benchmark and scale.

Request path, and where the time goes:

    arrival -> [shed?] -> [queue] -> [cache] -> [retrieve] -> [generate] -> done
               |__________________|            |_________________________|
                     QUEUE WAIT                        COMPUTE

The whole activity turns on being able to see those two numbers separately.
An overloaded queue and a slow model look identical from the outside and have
opposite fixes.
"""
import asyncio
import importlib
import json
import os
import pathlib
import secrets
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import config          # noqa: E402
import levers          # noqa: E402
import retrieval       # noqa: E402
from timing import Timer  # noqa: E402

if config.MODEL_BACKEND == "google":
    import cloud_model as model  # noqa: E402
else:
    import torch  # noqa: E402
    import model  # noqa: E402

    # One core per in-flight request in local mode. Cloud mode is network-bound
    # and does not import PyTorch for LLM inference.
    torch.set_num_threads(1)

_state: dict = {"semaphore": None, "waiting": 0, "served": 0, "shed": 0, "failed": 0}

_CONFIG_KEYS = ("MODEL_BACKEND", "RESPONSE_CACHE", "PREFIX_CACHE", "SEMANTIC_CACHE",
                "SEMANTIC_CACHE_THRESHOLD", "MAX_TOKENS",
                "SYSTEM_PROMPT", "RETRIEVE_K", "ROUTE_EASY", "MODEL_TIER",
                "MAX_CONCURRENT", "REPLICAS", "SHED_ABOVE_QUEUE")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate/load all runtime dependencies BEFORE serving traffic, never inside
    # a request handler. In Cloud Run this validates ADC; in local mode it loads
    # the two local model tiers.
    model.warm()
    _state["semaphore"] = asyncio.Semaphore(config.MAX_CONCURRENT * config.REPLICAS)
    print(f"Nimbus ready | {retrieval.size()} note chunks | tier={config.MODEL_TIER} "
          f"concurrency={config.MAX_CONCURRENT}x{config.REPLICAS} "
          f"max_tokens={config.MAX_TOKENS}")
    yield
    if hasattr(model, "close"):
        await model.close()


app = FastAPI(title="Nimbus", version="1.0", lifespan=lifespan)


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    max_tokens: int | None = Field(default=None, ge=1, le=1024)


@app.get("/", include_in_schema=False)
async def participant_ui() -> FileResponse:
    return FileResponse(pathlib.Path(__file__).resolve().parent / "web" / "index.html")


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "served": _state["served"],
            "shed": _state["shed"], "failed": _state["failed"],
            "waiting": _state["waiting"]}


def _admin_allowed(token: str | None) -> bool:
    expected = os.environ.get("NIMBUS_ADMIN_TOKEN")
    # Preserve the original local workflow. Cloud mode must be configured with
    # a secret, otherwise administrative endpoints are unavailable.
    if not expected:
        return config.MODEL_BACKEND != "google"
    return token is not None and secrets.compare_digest(token, expected)


@app.get("/metrics")
async def metrics(x_nimbus_admin_token: str | None = Header(default=None)) -> dict:
    if not _admin_allowed(x_nimbus_admin_token):
        return JSONResponse({"error": "admin authentication required"}, status_code=401)
    return {
        "served": _state["served"], "shed": _state["shed"],
        "failed": _state["failed"],
        "waiting": _state["waiting"],
        "config": {k: getattr(config, k) for k in _CONFIG_KEYS},
        "runtime": (model.runtime_info() if hasattr(model, "runtime_info") else
                    {"provider": "local"}),
        "cache": levers.cache_stats(),
    }


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


@app.post("/reload")
async def reload_config(x_nimbus_admin_token: str | None = Header(default=None)) -> dict:
    """Re-read config.py without restarting.

    In local mode, loading both model tiers takes ~13s. Cloud mode validates
    credentials at startup and keeps the managed model warm outside this
    process, so reload remains a configuration/cache operation.
    importlib.reload updates the existing module object in place, so levers.py --
    which holds a reference to it and reads config.X at call time -- sees the new
    values without being reloaded itself.

    Caches are cleared deliberately: a lever change should be measured against a
    cold cache, not against answers accumulated under the previous settings.
    """
    if not _admin_allowed(x_nimbus_admin_token):
        return JSONResponse({"error": "admin authentication required"}, status_code=401)
    try:
        importlib.reload(config)
    except Exception as exc:  # noqa: BLE001
        # Participants edit this file by hand under time pressure. A stray comma
        # should produce a sentence they can act on, not a stack trace -- and the
        # server must keep serving with the last good config.
        return JSONResponse(
            {"reloaded": False,
             "error": f"{type(exc).__name__}: {exc}",
             "hint": "config.py has a syntax error. Fix it and run `make reload` "
                     "again. The server is still running the previous config."},
            status_code=400)

    levers.reset_caches()
    _state["semaphore"] = asyncio.Semaphore(config.MAX_CONCURRENT * config.REPLICAS)
    _state["served"] = _state["shed"] = _state["failed"] = 0
    return {"reloaded": True,
            "config": {k: getattr(config, k) for k in _CONFIG_KEYS}}


@app.post("/ask")
async def ask(body: Ask):
    timer = Timer()

    # ── Rung 6 · load shedding ───────────────────────────────────────────
    # Fail fast and honestly rather than time out slowly. Every shed request
    # is still a student who did not get an answer.
    if config.SHED_ABOVE_QUEUE is not None and _state["waiting"] > config.SHED_ABOVE_QUEUE:
        _state["shed"] += 1
        return JSONResponse(
            {"error": "overloaded", "retry_after_s": 2},
            status_code=429,
            headers={"Retry-After": "2", "X-Queue-Depth": str(_state["waiting"])},
        )

    # ── Rung 5 · admission control ───────────────────────────────────────
    semaphore = _state["semaphore"]
    if semaphore is None:
        return JSONResponse({"error": "service is still starting"}, status_code=503)
    _state["waiting"] += 1
    try:
        await semaphore.acquire()
    finally:
        _state["waiting"] -= 1
    timer.admitted()

    max_tokens = body.max_tokens if body.max_tokens is not None else config.MAX_TOKENS
    question = body.question

    async def stream():
        stats = {"tokens_in": 0, "tokens_out": 0, "usage_source": "local"}
        cache_state, tier = "miss", "-"
        try:
            # ── Rung 2 · caches, cheapest first ──────────────────────────
            # The semantic cache is checked first because a hit skips
            # retrieval AND generation. The exact cache is keyed on the
            # assembled prompt, so it can only be checked after retrieval.
            with timer.stage("cache"):
                qvec = levers.question_vector(question)
                answer = levers.semantic_get(question, qvec)
            if answer is not None:
                cache_state = "semantic-hit"
                prompt = None
            else:
                with timer.stage("retrieve"):
                    chunks = retrieval.search(question, config.RETRIEVE_K)
                with timer.stage("assemble"):
                    prompt = levers.build_prompt(question, chunks)
                with timer.stage("cache"):
                    answer = levers.exact_get(prompt)
                if answer is not None:
                    cache_state = "exact-hit"

            if answer is not None:
                yield _sse({"delta": answer})
            else:
                tier = levers.pick_tier(question)
                pieces = []
                with timer.stage("generate"):
                    prefix = levers.static_prefix() if config.PREFIX_CACHE else None
                    async for chunk in model.generate(tier, prompt, max_tokens,
                                                      stats, prefix):
                        pieces.append(chunk)
                        yield _sse({"delta": chunk})
                answer = "".join(pieces)
                levers.exact_put(prompt, answer)
                levers.semantic_put(question, answer, qvec)

            _state["served"] += 1
            yield _sse({"stats": {
                "queue_wait_ms": round(timer.queue_wait_ms, 1),
                "compute_ms": round(timer.compute_ms, 1),
                "stages_ms": {k: round(v * 1000, 1) for k, v in timer.stages.items()},
                "tokens_in": stats["tokens_in"],
                "tokens_out": stats["tokens_out"],
                "tokens_cached": stats.get("tokens_cached", 0),
                "usage_source": stats.get("usage_source", "unknown"),
                "provider": stats.get("provider", "local"),
                "model": stats.get("model", ""),
                "cache": cache_state,
                "tier": tier,
            }})
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            _state["failed"] += 1
            print(f"Nimbus request failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            # The HTTP status is already 200 once a stream starts. Emit a
            # machine-readable event so browsers and benchmarks do not mistake
            # a truncated stream for a successful answer.
            yield _sse({"error": {
                "code": "request_failed",
                "message": "Nimbus could not complete this request. Please try again.",
            }})
            yield "data: [DONE]\n\n"
        finally:
            # Capture the semaphore this request acquired. /reload may replace
            # the global semaphore while a streamed request is still running.
            semaphore.release()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache",
                 "X-Accel-Buffering": "no",
                 "X-Queue-Wait-Ms": f"{timer.queue_wait_ms:.1f}"},
    )
