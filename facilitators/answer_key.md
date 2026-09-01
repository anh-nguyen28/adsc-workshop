# Answer Key — measured, not guessed

**Not for participants.**

Every number here came from running the ladder. Regenerate after any change to the corpus, model tiers, prompt, or request count:

```bash
make serve                                      # terminal 1
.venv/bin/python facilitators/calibrate.py      # terminal 2, ~5 min
.venv/bin/python facilitators/eval_all.py       # ~15 min
.venv/bin/python facilitators/make_answer_key.py
```

> ⚠ **Latency is hardware-dependent.** These came from a 4-core Apple Silicon laptop; a 2-core Codespace is roughly 2× slower. **Cost is not** — it is computed from token counts, so it transfers. Re-measure latency on the hardware the room will actually use, and reset the SLO from that.

---

## The ladder    (SLO p95 ≤ 5.0s · budget ≤ $1,500/mo · quality ≥ 80%)

| Rung | p95 | queue | compute | resp-cache | $/mo | run | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| **1 baseline** | 25.19s | 18.01s | 7.41s | 0% | $2,697 | 48s | 0/2 (lat FAIL, cost FAIL) |
| **2 caching** | 11.09s | 8.56s | 4.46s | 50% | $817 | 17s | 1/2 (lat FAIL, cost PASS) |
| **3 less work** | 6.68s | 5.51s | 3.27s | 50% | $645 | 11s | 1/2 (lat FAIL, cost PASS) |
| **4 routing** | 3.29s | 1.94s | 1.53s | 50% | $402 | 6s | 2/2 (lat PASS, cost PASS) |
| **5 concurrency** | 3.86s | 0.64s | 3.86s | 50% | $402 | 7s | 2/2 (lat PASS, cost PASS) |
| **6 replicas** | 8.13s | 0.00s | 8.05s | 31% | $712 | 11s | 1/2 (lat FAIL, cost PASS) |
| **X the trap** | 11.56s | 8.64s | 3.16s | 0% | $500 | 23s | 1/2 (lat FAIL, cost PASS) |

---

## What each rung teaches

**Rung 1 — confirm.** Baseline queue wait is far above compute. The model is not the problem: the service admits two requests at a time while eight are arriving. Teams that read this correctly fix it for free. Teams that do not go and buy capacity they never needed.

**Rung 2 — caching.** Three different things, and they should be turned on one at a time. `RESPONSE_CACHE` stores finished answers (a hit costs nothing at all). `PREFIX_CACHE` is real prompt caching — the attention cache for the static prompt block is computed once and reused, so input tokens bill at 10% and prefill is skipped; generation still costs full price. `SEMANTIC_CACHE` catches re-phrasings the exact cache misses.

**Rung 3 — less work.** The 1,200-token system prompt is re-read on every request and nobody had audited it. See the eval card: trimming it did not cost quality.

**Rung 4 — routing.** Easy questions to the small model, hard ones stay on the large one. Measured quality cost: 94% → 92%, still above the 80% bar.

**Rung 5 — concurrency.** Free, and it helps only up to the number of cores. Raising it past that does not create capacity, it just relocates the waiting.

**Rung 6 — replicas.** The only lever with a bill attached: $300/month each, whether or not anyone uses it. Compare rungs 5 and 6 in the table above and note what the extra $300 actually bought.

**Rung X — the trap.** `MODEL_TIER = "small"` scores 78% on the eval, against a 80% bar. Let tables try it — then send them to the eval card. It is the teaching moment, not a wrong answer to shut down.

---

## Reveal talking points

- **The cheap fixes were the effective ones.** Caching and prompt trimming cost nothing and did most of the work.
- **One production team** moved a single dynamic identifier from the middle of their prompt to the end, took their prefix-cache hit rate from 7% to 74%, and cut their monthly bill 59%. Same prompt, different order — which is exactly why `build_prompt` puts the static block first.
- **Continuous batching** takes Llama-70B serving from roughly $0.60–0.80 to $0.15–0.25 per million tokens on the same hardware.
- **Capacity last.** Fairgen cut GPU infrastructure cost 70% without changing their model or serving framework at all.
- **The trap in the wild:** teams that swap 70B → 7B without measuring cut cost ~90% and watch quality collapse on the hard requests.

**Closing line:** *Scaling is diagnosis first. The cheapest fix is usually a config change — not a bigger bill, and not a worse model.*
