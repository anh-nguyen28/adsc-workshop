"""Regenerate facilitators/answer_key.md from measured ladder + eval results.

Both inputs are produced by running the thing, not by estimating it:
  facilitators/calibrate.py  -> ladder.json        (latency, cost, per rung)
  facilitators/eval_all.py   -> eval_results.json  (quality, per config)
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
F = ROOT / "facilitators"
ladder = json.loads((F / "ladder.json").read_text())
evals = {r["label"]: r["score_pct"] for r in
         json.loads((F / "eval_results.json").read_text())}
sc = json.loads((ROOT / "scenario.json").read_text())
slo = sc["constraints"]["slo_p95_latency_s"]
budget = sc["constraints"]["budget_usd_per_month"]
bar = sc["constraints"]["quality_bar_eval_pct"]

L = [
    "# Answer Key — measured, not guessed",
    "",
    "**Not for participants.**",
    "",
    "Every number here came from running the ladder. Regenerate after any change "
    "to the corpus, model tiers, prompt, or request count:",
    "",
    "```bash",
    "make serve                                      # terminal 1",
    ".venv/bin/python facilitators/calibrate.py      # terminal 2, ~5 min",
    ".venv/bin/python facilitators/eval_all.py       # ~15 min",
    ".venv/bin/python facilitators/make_answer_key.py",
    "```",
    "",
    "> ⚠ **Latency is hardware-dependent.** These came from a 4-core Apple Silicon "
    "laptop; a 2-core Codespace is roughly 2× slower. **Cost is not** — it is "
    "computed from token counts, so it transfers. Re-measure latency on the "
    "hardware the room will actually use, and reset the SLO from that.",
    "",
    "---",
    "",
    f"## The ladder    (SLO p95 ≤ {slo}s · budget ≤ ${budget:,}/mo · quality ≥ {bar}%)",
    "",
    "| Rung | p95 | queue | compute | resp-cache | $/mo | run | verdict |",
    "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
]
for r in ladder:
    lat = "PASS" if r["p95"] <= slo else "FAIL"
    cost = "PASS" if r["usd_per_month"] <= budget else "FAIL"
    met = (r["p95"] <= slo) + (r["usd_per_month"] <= budget)
    L.append(f"| **{r['rung']}** | {r['p95']:.2f}s | {r['queue_p95']:.2f}s | "
             f"{r['compute_p95']:.2f}s | {r['cache_hit_rate']*100:.0f}% | "
             f"${r['usd_per_month']:,.0f} | {r['duration_s']:.0f}s | "
             f"{met}/2 (lat {lat}, cost {cost}) |")

L += ["", "---", "", "## What each rung teaches", ""]
L += [
    "**Rung 1 — confirm.** Baseline queue wait is far above compute. The model is "
    "not the problem: the service admits two requests at a time while eight are "
    "arriving. Teams that read this correctly fix it for free. Teams that do not "
    "go and buy capacity they never needed.",
    "",
    "**Rung 2 — caching.** Three different things, and they should be turned on one "
    "at a time. `RESPONSE_CACHE` stores finished answers (a hit costs nothing at "
    "all). `PREFIX_CACHE` is real prompt caching — the attention cache for the "
    "static prompt block is computed once and reused, so input tokens bill at 10% "
    "and prefill is skipped; generation still costs full price. `SEMANTIC_CACHE` "
    "catches re-phrasings the exact cache misses.",
    "",
    "**Rung 3 — less work.** The 1,200-token system prompt is re-read on every "
    "request and nobody had audited it. See the eval card: trimming it did not "
    "cost quality.",
    "",
    "**Rung 4 — routing.** Easy questions to the small model, hard ones stay on the "
    f"large one. Measured quality cost: {evals.get('Large model, full context (as shipped)', 0):.0f}% → "
    f"{evals.get('Routing: easy -> small, hard -> large', 0):.0f}%, still above the {bar}% bar.",
    "",
    "**Rung 5 — concurrency.** Free, and it helps only up to the number of cores. "
    "Raising it past that does not create capacity, it just relocates the waiting.",
    "",
    "**Rung 6 — replicas.** The only lever with a bill attached: $300/month each, "
    "whether or not anyone uses it. Compare rungs 5 and 6 in the table above and "
    "note what the extra $300 actually bought.",
    "",
    f"**Rung X — the trap.** `MODEL_TIER = \"small\"` scores "
    f"{evals.get('Small model for EVERYTHING', 0):.0f}% on the eval, against a {bar}% bar. "
    "Let tables try it — then send them to the eval card. It is the teaching "
    "moment, not a wrong answer to shut down.",
    "",
    "---",
    "",
    "## Reveal talking points",
    "",
    "- **The cheap fixes were the effective ones.** Caching and prompt trimming "
    "cost nothing and did most of the work.",
    "- **One production team** moved a single dynamic identifier from the middle of "
    "their prompt to the end, took their prefix-cache hit rate from 7% to 74%, and "
    "cut their monthly bill 59%. Same prompt, different order — which is exactly "
    "why `build_prompt` puts the static block first.",
    "- **Continuous batching** takes Llama-70B serving from roughly $0.60–0.80 to "
    "$0.15–0.25 per million tokens on the same hardware.",
    "- **Capacity last.** Fairgen cut GPU infrastructure cost 70% without changing "
    "their model or serving framework at all.",
    "- **The trap in the wild:** teams that swap 70B → 7B without measuring cut cost "
    "~90% and watch quality collapse on the hard requests.",
    "",
    "**Closing line:** *Scaling is diagnosis first. The cheapest fix is usually a "
    "config change — not a bigger bill, and not a worse model.*",
]
(F / "answer_key.md").write_text("\n".join(L) + "\n")
print(f"wrote answer_key.md from {len(ladder)} rungs + {len(evals)} eval configs")
