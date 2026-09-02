"""Turn raw per-request timings into the thing the room actually reads.

The important design decision here is the VERDICT. A benchmark that only prints
numbers is a measurement tool; one that says PASS or FAIL against a stated SLO
and a stated budget is a game with a win condition, and people play it.
"""
import json
import os
import pathlib


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(int(round(q / 100 * (len(ordered) - 1))), len(ordered) - 1)
    return ordered[idx]


def _price_for(row: dict, payload: dict, scenario: dict) -> dict | None:
    """Find a token price for the backend that actually served the request."""
    provider = row.get("provider") or payload.get("server_runtime", {}).get("provider", "local")
    model = row.get("model") or ""
    provider_prices = scenario.get("provider_prices", {})
    if model and f"{provider}:{model}" in provider_prices:
        return provider_prices[f"{provider}:{model}"]
    if provider == "local":
        tier = row.get("tier")
        return scenario.get("prices", {}).get(tier)
    return None


def summarise(payload: dict, scenario: dict) -> dict:
    rows = payload["results"]
    ok = [r for r in rows if r.get("ok")]
    shed = [r for r in rows if r.get("shed")]
    failed = [r for r in rows if not r.get("ok") and not r.get("shed")]
    duration = payload["duration_s"]

    prices = scenario["prices"]
    token_cost = 0.0
    cached_tokens = 0
    unknown_usage_requests = 0
    for r in ok:
        price = _price_for(r, payload, scenario)
        provider = r.get("provider") or payload.get("server_runtime", {}).get("provider", "local")
        usage_source = r.get("usage_source", "local" if provider == "local" else "unknown")
        has_usage = usage_source not in {"unreported", "unknown", None}
        is_cache_hit = r.get("cache", "miss") != "miss"
        if is_cache_hit:
            # A cache hit performs no model call and therefore costs no model
            # tokens, even if the configured model has no price entry here.
            continue
        if price is None or not has_usage:
            unknown_usage_requests += 1
            continue
        # Prefix-cached tokens are still input tokens -- they are simply billed
        # at the discounted rate, exactly as a provider would charge them.
        cached = min(r.get("tokens_cached", 0), r["tokens_in"])
        fresh = r["tokens_in"] - cached
        cached_tokens += cached
        token_cost += (fresh / 1e6) * price["input"]
        token_cost += (cached / 1e6) * price.get("cached_input", price["input"])
        token_cost += (r["tokens_out"] / 1e6) * price["output"]

    n = max(len(ok), 1)
    usage_complete = unknown_usage_requests == 0
    per_request = token_cost / n if usage_complete else None
    monthly_requests = scenario["traffic"]["requests_per_day"] * 30

    provider = payload.get("server_runtime", {}).get("provider")
    if not provider:
        providers = {r.get("provider") for r in ok if r.get("provider")}
        provider = "google" if "google" in providers else next(iter(providers), "local")
    if provider == "google":
        # Cloud Run cost depends on CPU/memory allocation and active time, so a
        # flat "replica" price would be misleading. Let the operator provide a
        # budget estimate when they know the service shape; otherwise report it
        # as separate/unknown rather than silently calling token cost total cost.
        estimate = os.environ.get("NIMBUS_CLOUD_RUN_MONTHLY_ESTIMATE_USD")
        infra = float(estimate) if estimate is not None else None
        replicas = None
    else:
        # Capacity is the only lever with a bill in the local exercise.
        replicas = payload.get("server_config", {}).get("REPLICAS", 1) or 1
        infra = replicas * prices.get("replica_usd_per_month", 0)
    hits = sum(1 for r in ok if r.get("cache", "miss") != "miss")

    monthly_token_cost = token_cost / n * monthly_requests if usage_complete else None
    monthly_total = (monthly_token_cost + infra
                     if monthly_token_cost is not None and infra is not None else None)

    return {
        "run": payload["run"],
        "label": payload.get("label", ""),
        "ok": len(ok), "shed": len(shed), "failed": len(failed),
        "duration_s": duration,
        "rps": len(ok) / duration if duration else 0.0,
        "tps": sum(r["tokens_out"] for r in ok) / duration if duration else 0.0,
        "p50": pct([r["latency_s"] for r in ok], 50),
        "p90": pct([r["latency_s"] for r in ok], 90),
        "p95": pct([r["latency_s"] for r in ok], 95),
        "p99": pct([r["latency_s"] for r in ok], 99),
        "ttft_p95": pct([r["ttft_s"] for r in ok], 95),
        "queue_p95": pct([r["queue_wait_ms"] for r in ok], 95) / 1000,
        "compute_p95": pct([r["compute_ms"] for r in ok], 95) / 1000,
        "cache_hit_rate": hits / n,
        "prefix_cached_tokens": cached_tokens,
        "input_tokens": sum(r["tokens_in"] for r in ok),
        "usage_complete": usage_complete,
        "unknown_usage_requests": unknown_usage_requests,
        "usd_token_cost_per_1k": token_cost / n * 1000,
        "usd_per_1k": per_request * 1000 if per_request is not None else None,
        "replicas": replicas,
        "usd_tokens_per_month": monthly_token_cost,
        "usd_infra_per_month": infra,
        "usd_per_month": monthly_total,
    }


def render(payload: dict, scenario: dict, results_dir: pathlib.Path) -> str:
    s = summarise(payload, scenario)
    c = scenario["constraints"]
    slo, budget = c["slo_p95_latency_s"], c["budget_usd_per_month"]

    # A run with no successful requests is a failed deployment, not a pass.
    # Percentiles over an empty list are 0.0, and 0.0 <= any SLO -- so without
    # this guard a completely broken service reports "2/2 constraints met".
    healthy = s["ok"] > 0
    lat_ok = healthy and s["p95"] <= slo
    cost_ok = healthy and s["usd_per_month"] is not None and s["usd_per_month"] <= budget
    met = int(lat_ok) + int(cost_ok)

    # Repeated runs of an identical config on this workload vary by ~12%. A
    # result inside that band is not a result -- it is noise that happens to
    # have landed on one side of the line. Say so rather than pretending.
    NOISE = 0.15
    lat_marginal = healthy and abs(s["p95"] - slo) / slo < NOISE
    cost_marginal = (healthy and s["usd_per_month"] is not None and
                     abs(s["usd_per_month"] - budget) / budget < NOISE)

    prev = None
    prev_path = results_dir / f"run-{payload['run'] - 1}.json"
    if prev_path.exists():
        prev = summarise(json.loads(prev_path.read_text()), scenario)

    def mark(ok: bool, marginal: bool = False) -> str:
        if marginal:
            return "MARGINAL"
        return "PASS" if ok else "FAIL"

    w = 68
    L = []
    label = f"  {s['label']}" if s["label"] else ""
    L.append("")
    L.append(f"NIMBUS BENCHMARK - run {s['run']}{label}")
    L.append("=" * w)
    L.append(f"requests     {s['ok']} ok · {s['shed']} shed · {s['failed']} failed"
             f"{'':>6}duration  {s['duration_s']:.1f} s")
    L.append(f"throughput   {s['rps']:.1f} req/s · {s['tps']:.0f} output tok/s")
    L.append("")
    L.append(f"latency      median   {s['p50']:6.2f} s")
    L.append(f"             p95      {s['p95']:6.2f} s   SLO {slo:.2f} s   "
             f"{mark(lat_ok, lat_marginal)}")
    L.append(f"             slowest  {s['p99']:6.2f} s")
    L.append(f"TTFT         p95      {s['ttft_p95']:6.2f} s")
    if s["ok"] < 50:
        rank = s["ok"] - int(round(0.95 * (s["ok"] - 1)))
        L.append(f"             note: with {s['ok']} requests, \"p95\" is the "
                 f"{rank}{'nd' if rank == 2 else 'st' if rank == 1 else 'th'}-slowest")
        L.append(f"             request, not a true percentile. Repeat runs vary ~12%.")
    L.append("")
    L.append("             ── where the time went ──")
    L.append(f"queue wait   p95   {s['queue_p95']:6.2f} s   <- waiting in line")
    L.append(f"compute      p95   {s['compute_p95']:6.2f} s   <- actually working")
    L.append(f"cache        response hit rate {s['cache_hit_rate']*100:.0f}%")
    if s["input_tokens"]:
        share = s["prefix_cached_tokens"] / s["input_tokens"] * 100
        L.append(f"             prefix-cached input {share:.0f}% "
                 f"({s['prefix_cached_tokens']:,} of {s['input_tokens']:,} tokens)")
    L.append("")
    if s["usage_complete"]:
        L.append(f"cost         ${s['usd_per_1k']:.3f} / 1k requests")
        if s["replicas"] is not None:
            infra_label = (f"${s['usd_infra_per_month']:,.0f} infra "
                           f"({s['replicas']} replica"
                           f"{'s' if s['replicas'] != 1 else ''})")
        elif s["usd_infra_per_month"] is not None:
            infra_label = f"${s['usd_infra_per_month']:,.0f} Cloud Run estimate"
        else:
            infra_label = "Cloud Run infra not supplied"
        token_label = f"${s['usd_tokens_per_month']:,.0f} tokens"
        total_label = (f"${s['usd_per_month']:,.0f} / month"
                       if s["usd_per_month"] is not None else
                       "total / month unknown")
        L.append(f"             {token_label} + {infra_label}")
        L.append(f"             {total_label} @ {scenario['traffic']['requests_per_day']:,}/day"
                 f"   budget ${budget:,}   {mark(cost_ok, cost_marginal) if s['usd_per_month'] is not None else 'UNKNOWN'}")
    else:
        L.append("cost         UNKNOWN — provider usage was not reported for "
                 f"{s['unknown_usage_requests']} request(s)")
        L.append("             set provider usage reporting or do not use this run "
                 "for the budget verdict")
    L.append("")
    L.append("-" * w)
    verdict = f"VERDICT  {met}/2 constraints met"
    if lat_marginal or cost_marginal:
        verdict += "  -- but within measurement noise. Run it again before believing it."
    if prev:
        previous_cost = (f"${prev['usd_per_month']:,.0f}/mo"
                         if prev["usd_per_month"] is not None else "cost unknown")
        verdict += (f"      (run {prev['run']}: p95 {prev['p95']:.2f}s, "
                    f"{previous_cost})")
    L.append(verdict)

    if not healthy:
        L.append("hint     every request failed. Is `make serve` running, and on this port?")
    elif not lat_ok and s["queue_p95"] > s["compute_p95"]:
        L.append("hint     queue wait exceeds compute. The model is not your problem.")
    elif not lat_ok:
        L.append("hint     compute dominates. Each request is doing too much work.")
    L.append("")
    return "\n".join(L)
