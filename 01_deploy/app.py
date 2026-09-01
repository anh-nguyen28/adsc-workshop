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
import pathlib
import sys
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import config          # noqa: E402
import levers          # noqa: E402
import model           # noqa: E402
import retrieval       # noqa: E402
from timing import Timer  # noqa: E402

# One core per in-flight request. This is what makes MAX_CONCURRENT a real
# lever: the box has a fixed number of cores, so admitting more work than that
# does not create capacity -- it just relocates the waiting.
torch.set_num_threads(1)

_state: dict = {"semaphore": None, "waiting": 0, "served": 0, "shed": 0}

_CONFIG_KEYS = ("RESPONSE_CACHE", "PREFIX_CACHE", "SEMANTIC_CACHE", "MAX_TOKENS",
                "SYSTEM_PROMPT", "RETRIEVE_K", "ROUTE_EASY", "MODEL_TIER",
                "MAX_CONCURRENT", "REPLICAS", "SHED_ABOVE_QUEUE")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load every model tier BEFORE serving traffic, never inside a handler.
    model.warm()
    _state["semaphore"] = asyncio.Semaphore(config.MAX_CONCURRENT * config.REPLICAS)
    print(f"Nimbus ready | {retrieval.size()} note chunks | tier={config.MODEL_TIER} "
          f"concurrency={config.MAX_CONCURRENT}x{config.REPLICAS} "
          f"max_tokens={config.MAX_TOKENS}")
    yield


app = FastAPI(title="Nimbus", version="1.0", lifespan=lifespan)


class Ask(BaseModel):
    question: str
    max_tokens: int | None = None


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "served": _state["served"],
            "shed": _state["shed"], "waiting": _state["waiting"]}


@app.get("/metrics")
async def metrics() -> dict:
    return {
        "served": _state["served"], "shed": _state["shed"],
        "waiting": _state["waiting"],
        "config": {k: getattr(config, k) for k in _CONFIG_KEYS},
        "cache": levers.cache_stats(),
    }


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


@app.post("/reload")
async def reload_config() -> dict:
    """Re-read config.py without restarting.

    Loading both model tiers takes ~13s. Paying that on every lever change is a
    minute of dead time across the ladder, which is a minute not spent thinking.
    importlib.reload updates the existing module object in place, so levers.py --
    which holds a reference to it and reads config.X at call time -- sees the new
    values without being reloaded itself.

    Caches are cleared deliberately: a lever change should be measured against a
    cold cache, not against answers accumulated under the previous settings.
    """
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
    _state["served"] = _state["shed"] = 0
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
    _state["waiting"] += 1
    try:
        await _state["semaphore"].acquire()
    finally:
        _state["waiting"] -= 1
    timer.admitted()

    max_tokens = body.max_tokens or config.MAX_TOKENS
    question = body.question

    async def stream():
        stats = {"tokens_in": 0, "tokens_out": 0}
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
                "cache": cache_state,
                "tier": tier,
            }})
            yield "data: [DONE]\n\n"
        finally:
            _state["semaphore"].release()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"X-Queue-Wait-Ms": f"{timer.queue_wait_ms:.1f}"},
    )
