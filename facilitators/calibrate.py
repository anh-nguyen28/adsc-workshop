"""Measure every rung of the ladder for real, so the answer key is not guesswork.

Uses /reload rather than restarting the server, which turns a ~13s penalty per
configuration into nothing. Requires `make serve` to already be running.

Every rung states the FULL config, never a delta on whatever happens to be in
the file: an interrupted run leaves config.py patched, and reading that back as
a "baseline" silently produces a baseline with caching already on. Ask how I
know.
"""
import json, os, pathlib, re, subprocess, sys, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = ROOT / "01_deploy" / "config.py"
PY = str(ROOT / ".venv" / "bin" / "python")
URL = os.environ.get("NIMBUS_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_TOKEN = os.environ.get("NIMBUS_ADMIN_TOKEN", "")
ORIGINAL = CFG.read_text()

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from defaults import DEFAULTS  # noqa: E402  single source of truth


# Cumulative: each rung keeps what the previous rungs turned on, which is how a
# team actually climbs it.
_R2 = {"RESPONSE_CACHE": "True", "PREFIX_CACHE": "True", "SEMANTIC_CACHE": "True"}
_R3 = {**_R2, "SYSTEM_PROMPT": '"TRIMMED"', "MAX_TOKENS": "24", "RETRIEVE_K": "3"}
_R4 = {**_R3, "ROUTE_EASY": "True"}
_R5 = {**_R4, "MAX_CONCURRENT": "4"}
_R6 = {**_R5, "REPLICAS": "2"}

LADDER = [
    ("1 baseline",    {}),
    ("2 caching",     _R2),
    ("3 less work",   _R3),
    ("4 routing",     _R4),
    ("5 concurrency", _R5),
    ("6 replicas",    _R6),      # the only lever with a bill attached
    ("X the trap",    {"MODEL_TIER": '"small"'}),
]


def patch(overrides):
    src = ORIGINAL
    for k, v in {**DEFAULTS, **overrides}.items():
        src = re.sub(rf"^{k} = .*$", f"{k} = {v}", src, count=1, flags=re.M)
    CFG.write_text(src)


def reload_server():
    headers = {"X-Nimbus-Admin-Token": ADMIN_TOKEN} if ADMIN_TOKEN else {}
    req = urllib.request.Request(f"{URL}/reload", method="POST", data=b"", headers=headers)
    urllib.request.urlopen(req, timeout=180).read()


def main():
    try:
        urllib.request.urlopen(f"{URL}/health", timeout=5)
    except Exception:
        sys.exit("Nimbus is not running. Start `make serve` first.")

    sys.path.insert(0, str(ROOT / "02_benchmark"))
    from report import summarise  # noqa: PLC0415
    scenario = json.loads((ROOT / "scenario.json").read_text())
    results_dir = ROOT / "results"
    rows = []
    try:
        for name, overrides in LADDER:
            patch(overrides)
            reload_server()
            for f in results_dir.glob("*.json"):
                f.unlink()
            subprocess.run([PY, str(ROOT / "02_benchmark" / "run.py"), "--label", name],
                           cwd=ROOT, stdout=subprocess.DEVNULL, timeout=1800)
            s = summarise(json.loads((results_dir / "run-1.json").read_text()), scenario)
            rows.append({"rung": name, **s})
            print(f"{name:<14} p95 {s['p95']:6.2f}s | queue {s['queue_p95']:5.2f}s | "
                  f"compute {s['compute_p95']:6.2f}s | resp-cache {s['cache_hit_rate']*100:3.0f}% | "
                  f"${s['usd_per_month']:>6,.0f}/mo | {s['duration_s']:.0f}s", flush=True)
    finally:
        patch({})
        try:
            reload_server()
        except Exception:
            pass

    (ROOT / "facilitators" / "ladder.json").write_text(json.dumps(rows, indent=2))
    print("\n=== LADDER (measured) ===")
    print(f"{'rung':<14}{'p95':>8}{'queue':>8}{'compute':>9}{'cache':>7}{'$/mo':>10}{'run':>7}")
    for r in rows:
        print(f"{r['rung']:<14}{r['p95']:>7.2f}s{r['queue_p95']:>7.2f}s{r['compute_p95']:>8.2f}s"
              f"{r['cache_hit_rate']*100:>6.0f}%{r['usd_per_month']:>10,.0f}{r['duration_s']:>6.0f}s")


if __name__ == "__main__":
    main()
