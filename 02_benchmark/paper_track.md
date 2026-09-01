# Nimbus paper track — no laptop required

Use this if your table cannot run the service. You will make the same production
decisions as the coding track using fixed snapshots from a calibrated run.

> Numbers below are from a real calibration run (`facilitators/ladder.json`). Re-run `facilitators/calibrate.py` on the hardware the room will use and update this file — latency is hardware-dependent, cost is not.

## Incident brief

Nimbus, a university study assistant, has five times normal finals-week traffic.

| Constraint | Target | Baseline |
| --- | ---: | ---: |
| p95 latency | at most 5.0 s | 25.19 s |
| Monthly cost | at most $1,500 | $2,697 |
| Eval quality | at least 80% | see [eval card](eval_card.md) |

Your job is to recover latency and cost without breaking quality. Write your
choices in the [decision sheet](decision_sheet.md).

## Round 1 — diagnose before changing anything

| Metric | Baseline |
| --- | ---: |
| p95 latency | 25.19 s |
| Queue wait p95 | 18.01 s |
| Compute p95 | 7.41 s |
| Cache hit rate | 0% |
| Cost | $2,697/month |

1. Is this primarily a queue/capacity problem or a per-request compute problem?
2. Which number proves it?
3. What is the cheapest move you would test first?

## Round 2 — choose one move at a time

For each row, predict whether it helps latency, cost, quality, or some
combination. Reveal the measured result only after your table commits to an
answer.

| Move | Result after the move | Quality note |
| --- | --- | --- |
| Turn on `RESPONSE_CACHE`, `PREFIX_CACHE`, and `SEMANTIC_CACHE` | p95 11.09 s; queue 8.56 s; compute 4.46 s; cache 50%; $817/month | Semantic cache threshold stays 0.92, so quality clears. |
| Also use `SYSTEM_PROMPT = "TRIMMED"`, `MAX_TOKENS = 24`, `RETRIEVE_K = 3` | p95 6.68 s; queue 5.51 s; compute 3.27 s; $645/month | Reduced context must be checked on the eval. |
| Also turn on `ROUTE_EASY` | p95 3.29 s; queue 1.94 s; compute 1.53 s; $402/month | Easy questions use small; hard questions stay large. Both constraints now pass. |
| Also raise `MAX_CONCURRENT = 4` | p95 3.86 s; queue 0.64 s; compute 3.86 s; $402/month | Queue wait nearly vanishes, but CPU contention means total p95 does not improve. |
| Also set `REPLICAS = 2` | p95 8.13 s; queue 0.00 s; compute 8.05 s; $712/month | A second replica costs $300/month and makes p95 worse, not better. |

## Round 3 — the tempting wrong answer

Instead, set `MODEL_TIER = "small"` and leave every other lever at baseline.

| Metric | Result |
| --- | ---: |
| p95 latency | 17.53 s |
| Queue wait p95 | 13.70 s |
| Compute p95 | 5.57 s |
| Cost | $500/month |
| Eval quality | 67% |

Would you ship it? Explain using all three constraints, not only latency or
cost. Then use the [eval card](eval_card.md) to identify a version that passes
quality.

## Debrief

The low-cost path is: confirm the queue bottleneck → make repeated work free →
do less work per request → route easy work. It meets both operational
constraints before buying capacity. The small-model shortcut is not a win when
it violates the quality bar.
