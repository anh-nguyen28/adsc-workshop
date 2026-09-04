# Nimbus paper track — no laptop required

Use this if your table cannot reach the service. You make the same
diagnosis the coding track makes, from the same panel it would print.

> **Generated from measurement** on the `local` backend at 2026-09-03 20:16:46. Latency is hardware-dependent; token counts and
> shares are not. Regenerate with `facilitators/calibrate_incidents.py`
> followed by `facilitators/make_paper_track.py`.

## Your targets

| Constraint | Target |
| --- | ---: |
| p95 latency | at most 5.0 s |
| Monthly cost | at most $1,500 |
| Eval quality | at least 80% |

## How to use this

For each incident below: read the panel, decide **where the time went**,
then decide **what you would change**. Write both down before turning to
the facilitator's answer. The panel names the biggest contributor; it
deliberately does not name the fix.

---

## Finals week

**What was reported.** Every student is waiting, and it is worse at busy times.

**Who it affects.** Answers that used to arrive in seconds now take most of a minute.

```text
NIMBUS BENCHMARK - run 0  queue
====================================================================
requests     8 ok · 0 shed · 0 failed      duration  27.9 s
throughput   0.3 req/s · 9 output tok/s

latency      median    19.82 s
             p95       26.80 s   SLO 5.00 s   FAIL
             slowest   26.80 s
TTFT         p95       24.17 s
             note: with 8 requests, "p95" is the 1st-slowest
             request, not a true percentile. Repeat runs vary ~12%.
             8 of 8 request(s) exceeded the 5.0s target

             ── where the time went ─────────────────────────────
                      p95 req  p95 each
  client + network     0.00 s         -  ▏
  app queue wait      21.65 s    21.65s  ████████████████████████
  cache lookup         0.00 s     0.00s  ▏
  retrieve             0.02 s     0.04s  ▏
  assemble             0.00 s     0.00s  ▏
  generate             5.13 s     9.23s  ██████
  other (app)          0.00 s         -  ▏
                     --------
  sum of rows         26.80 s   end-to-end 26.80 s · residual +0.0%

             ── how the model behaved ───────────────────────────
  provider retries        0           upstream status: none
  provider            local

             ── work per request ────────────────────────────────
  input tokens          790 avg      baseline 242 · +227%
  output tokens          32 avg      baseline 32 · normal
  cache hit rate         0%
  prefix-cached          0%          0 of 6,324 input tokens

cost         $0.551 / 1k requests
             $2,480 tokens + $300 infra (1 replica)
             $2,780 / month @ 150,000/day   budget $1,500   FAIL

--------------------------------------------------------------------
VERDICT  0/2 constraints met
READ THIS FIRST
  Largest contributor to the p95 request: APP QUEUE WAIT (81%).
  Then: generate 19%.
  Below 1% of the budget: retrieve, client + network, other (app), cache lookup, assemble.
  At baseline: tokens out.
```

1. Which row is the largest contributor, and what is at baseline?
2. Is the model implicated? Which number settles it?
3. What is the one change you would make first?

---

## The new vector store

**What was reported.** Slow to START answering. The answer itself reads fine.

**Who it affects.** Students stare at a blank box, then get a good answer.

```text
NIMBUS BENCHMARK - run 0  retrieval
====================================================================
requests     8 ok · 0 shed · 0 failed      duration  20.5 s
throughput   0.4 req/s · 13 output tok/s

latency      median     4.43 s
             p95        7.76 s   SLO 5.00 s   FAIL
             slowest    7.76 s
TTFT         p95        6.51 s
             note: with 8 requests, "p95" is the 1st-slowest
             request, not a true percentile. Repeat runs vary ~12%.
             2 of 8 request(s) exceeded the 5.0s target

             ── where the time went ─────────────────────────────
                      p95 req  p95 each
  client + network     0.00 s         -  ▏
  app queue wait       0.00 s     0.00s  ▏
  cache lookup         0.00 s     0.00s  ▏
  retrieve             6.04 s     6.04s  ████████████████████████
  assemble             0.00 s     0.00s  ▏
  generate             1.71 s     2.59s  ███████
  other (app)          0.00 s         -  ▏
                     --------
  sum of rows          7.76 s   end-to-end 7.76 s · residual +0.0%

             ── how the model behaved ───────────────────────────
  provider retries        0           upstream status: none
  provider            local

             ── work per request ────────────────────────────────
  input tokens          242 avg      baseline 242 · normal
  output tokens          32 avg      baseline 32 · normal
  cache hit rate         0%
  prefix-cached          0%          0 of 1,932 input tokens

cost         $0.222 / 1k requests
             $998 tokens + $300 infra (1 replica)
             $1,298 / month @ 150,000/day   budget $1,500   MARGINAL

--------------------------------------------------------------------
VERDICT  1/2 constraints met  -- but within measurement noise. Run it again before believing it.
READ THIS FIRST
  Largest contributor to the p95 request: RETRIEVE (78%).
  Then: generate 22%.
  Below 1% of the budget: client + network, other (app), app queue wait, cache lookup, assemble.
  At baseline: tokens in, tokens out.
```

1. Which row is the largest contributor, and what is at baseline?
2. Is the model implicated? Which number settles it?
3. What is the one change you would make first?

---

## Tuesday's pull request

**What was reported.** The bill tripled. Latency is somewhat worse.

**Who it affects.** Finance noticed before engineering did.

```text
NIMBUS BENCHMARK - run 0  prompt
====================================================================
requests     8 ok · 0 shed · 0 failed      duration  34.8 s
throughput   0.2 req/s · 7 output tok/s

latency      median     8.59 s
             p95        9.82 s   SLO 5.00 s   FAIL
             slowest    9.82 s
TTFT         p95        6.01 s
             note: with 8 requests, "p95" is the 1st-slowest
             request, not a true percentile. Repeat runs vary ~12%.
             8 of 8 request(s) exceeded the 5.0s target

             ── where the time went ─────────────────────────────
                      p95 req  p95 each
  client + network     0.00 s         -  ▏
  app queue wait       0.00 s     0.00s  ▏
  cache lookup         0.00 s     0.00s  ▏
  retrieve             0.01 s     0.02s  ▏
  assemble             0.00 s     0.00s  ▏
  generate             9.80 s     9.80s  ████████████████████████
  other (app)          0.00 s         -  ▏
                     --------
  sum of rows          9.82 s   end-to-end 9.82 s · residual +0.0%

             ── how the model behaved ───────────────────────────
  provider retries        0           upstream status: none
  provider            local

             ── work per request ────────────────────────────────
  input tokens        1,217 avg      baseline 242 · +403%
  output tokens          32 avg      baseline 32 · normal
  cache hit rate         0%
  prefix-cached          0%          0 of 9,734 input tokens

cost         $0.807 / 1k requests
             $3,631 tokens + $300 infra (1 replica)
             $3,931 / month @ 150,000/day   budget $1,500   FAIL

--------------------------------------------------------------------
VERDICT  0/2 constraints met
READ THIS FIRST
  Largest contributor to the p95 request: GENERATE (100%).
  Below 1% of the budget: retrieve, client + network, app queue wait, other (app), cache lookup, assemble.
  At baseline: tokens out.
```

1. Which row is the largest contributor, and what is at baseline?
2. Is the model implicated? Which number settles it?
3. What is the one change you would make first?

---

## Helpfulness creep

**What was reported.** Answers begin instantly, then crawl to the end.

**Who it affects.** Students read the first line and wait for the rest.

```text
NIMBUS BENCHMARK - run 0  decode
====================================================================
requests     8 ok · 0 shed · 0 failed      duration  115.2 s
throughput   0.1 req/s · 15 output tok/s

latency      median    23.70 s
             p95       59.71 s   SLO 5.00 s   FAIL
             slowest   59.71 s
TTFT         p95        1.11 s
             note: with 8 requests, "p95" is the 1st-slowest
             request, not a true percentile. Repeat runs vary ~12%.
             7 of 8 request(s) exceeded the 5.0s target

             ── where the time went ─────────────────────────────
                      p95 req  p95 each
  client + network     0.01 s         -  ▏
  app queue wait       0.00 s     0.00s  ▏
  cache lookup         0.00 s     0.00s  ▏
  retrieve             0.01 s     0.15s  ▏
  assemble             0.00 s     0.00s  ▏
  generate            59.68 s    59.68s  ████████████████████████
  other (app)          0.00 s         -  ▏
                     --------
  sum of rows         59.71 s   end-to-end 59.71 s · residual +0.0%

             ── how the model behaved ───────────────────────────
  provider retries        0           upstream status: none
  provider            local

             ── work per request ────────────────────────────────
  input tokens          242 avg      baseline 242 · normal
  output tokens         214 avg      baseline 32 · +569%
  cache hit rate         0%
  prefix-cached          0%          0 of 1,932 input tokens

cost         $0.659 / 1k requests
             $2,965 tokens + $300 infra (1 replica)
             $3,265 / month @ 150,000/day   budget $1,500   FAIL

--------------------------------------------------------------------
VERDICT  0/2 constraints met
READ THIS FIRST
  Largest contributor to the p95 request: GENERATE (100%).
  Below 1% of the budget: client + network, retrieve, other (app), app queue wait, cache lookup, assemble.
  At baseline: tokens in.
```

1. Which row is the largest contributor, and what is at baseline?
2. Is the model implicated? Which number settles it?
3. What is the one change you would make first?

---

## Green dashboards

**What was reported.** Nobody has complained about speed. Tutors say the answers are wrong.

**Who it affects.** Students are confidently told the wrong thing.

```text
NIMBUS BENCHMARK - run 0  staleness
====================================================================
requests     8 ok · 0 shed · 0 failed      duration  8.6 s
throughput   0.9 req/s · 19 output tok/s

latency      median     2.38 s
             p95        3.50 s   SLO 5.00 s   PASS
             slowest    3.50 s
TTFT         p95        0.90 s
             note: with 8 requests, "p95" is the 1st-slowest
             request, not a true percentile. Repeat runs vary ~12%.

             ── where the time went ─────────────────────────────
                      p95 req  p95 each
  client + network     0.00 s         -  ▏
  app queue wait       0.00 s     0.00s  ▏
  cache lookup         0.01 s     0.01s  ▏
  retrieve             0.01 s     0.01s  ▏
  assemble             0.00 s     0.00s  ▏
  generate             3.48 s     3.48s  ████████████████████████
  other (app)          0.00 s         -  ▏
                     --------
  sum of rows          3.50 s   end-to-end 3.50 s · residual +0.0%

             ── how the model behaved ───────────────────────────
  provider retries        0           upstream status: none
  provider            local

             ── work per request ────────────────────────────────
  input tokens          239 avg      baseline 242 · normal
  output tokens          32 avg      baseline 32 · normal
  cache hit rate        38%
  prefix-cached          0%          0 of 1,197 input tokens

cost         $0.138 / 1k requests
             $620 tokens + $300 infra (1 replica)
             $920 / month @ 150,000/day   budget $1,500   PASS

--------------------------------------------------------------------
VERDICT  2/2 constraints met
READ THIS FIRST
  Largest contributor to the p95 request: GENERATE (99%).
  Below 1% of the budget: cache lookup, retrieve, client + network, other (app), app queue wait, assemble.
  At baseline: tokens in, tokens out.
```

1. Which row is the largest contributor, and what is at baseline?
2. Is the model implicated? Which number settles it?
3. What is the one change you would make first?

---

## The cheap-model shortcut

**What was reported.** Fast and cheap. Tutors say answers got shallow.

**Who it affects.** Simple questions are fine. The ones students actually struggle with are not.

```text
NIMBUS BENCHMARK - run 0  cheapmodel
====================================================================
requests     8 ok · 0 shed · 0 failed      duration  7.1 s
throughput   1.1 req/s · 36 output tok/s

latency      median     1.72 s
             p95        2.05 s   SLO 5.00 s   PASS
             slowest    2.05 s
TTFT         p95        0.66 s
             note: with 8 requests, "p95" is the 1st-slowest
             request, not a true percentile. Repeat runs vary ~12%.

             ── where the time went ─────────────────────────────
                      p95 req  p95 each
  client + network     0.00 s         -  ▏
  app queue wait       0.00 s     0.00s  ▏
  cache lookup         0.00 s     0.00s  ▏
  retrieve             0.01 s     0.02s  ▏
  assemble             0.00 s     0.00s  ▏
  generate             2.03 s     2.03s  ████████████████████████
  other (app)          0.00 s         -  ▏
                     --------
  sum of rows          2.05 s   end-to-end 2.05 s · residual +0.0%

             ── how the model behaved ───────────────────────────
  provider retries        0           upstream status: none
  provider            local

             ── work per request ────────────────────────────────
  input tokens          242 avg      baseline 242 · normal
  output tokens          32 avg      baseline 32 · normal
  cache hit rate         0%
  prefix-cached          0%          0 of 1,932 input tokens

cost         $0.018 / 1k requests
             $83 tokens + $300 infra (1 replica)
             $383 / month @ 150,000/day   budget $1,500   PASS

--------------------------------------------------------------------
VERDICT  2/2 constraints met
READ THIS FIRST
  Largest contributor to the p95 request: GENERATE (99%).
  Below 1% of the budget: retrieve, client + network, app queue wait, other (app), cache lookup, assemble.
  At baseline: tokens in, tokens out.
```

1. Which row is the largest contributor, and what is at baseline?
2. Is the model implicated? Which number settles it?
3. What is the one change you would make first?

---

## Facilitator answers

*Fold this section back, or print the pages above on their own.*

**Finals week** — Admission control (2) is far below the arrival concurrency (8).

- Tell: app queue wait dominates while token counts sit at baseline
- Tempting wrong fix: Blame the model and downgrade the tier.
- Correct path: Remove work from the queue (caching), then route, then capacity.

**The new vector store** — Course notes moved to a hosted vector store with a reranker. Correct, better, and p95 1.8s with a fat tail.

- Tell: retrieve is the dominant ledger row; generate is at baseline
- Tempting wrong fix: Downgrade the model or cut MAX_TOKENS -- both are falsifiable in one run, because neither touches the stage that is actually slow.
- Correct path: The semantic cache is checked BEFORE retrieval, so a hit skips the slow dependency entirely.

**Tuesday's pull request** — A 'better grounding' change took RETRIEVE_K from 4 to 12.

- Tell: input tokens far above baseline; output tokens unchanged
- Tempting wrong fix: Add capacity. Latency improves slightly and the monthly number gets worse, because the regression is per-request and capacity multiplies it.
- Correct path: Trim the prompt and the retrieved context; then check quality.

**Helpfulness creep** — MAX_TOKENS was raised 32 -> 256 to stop mid-sentence cutoffs.

- Tell: output tokens far above baseline, with generate dominant
- Tempting wrong fix: Turn on every cache. The tail of the corpus is mostly unique questions, so the hit rate barely moves and neither does p95.
- Correct path: Cap the output, then route. This is where the cheap-model shortcut is genuinely on the table -- and where the eval card fires.

**Green dashboards** — The similarity threshold was loosened 0.92 -> 0.55 to lift hit rate.

- Tell: every infrastructure signal PASSES; quality fails across BOTH extraction and reasoning
- Tempting wrong fix: Ship it. Nothing in the benchmark objects.
- Correct path: Run the eval. Notice the hit rate was the only number that looked too good.

**The cheap-model shortcut** — Every request goes to the small model.

- Tell: quality fails on REASONING while extraction holds -- the small model can still copy a fact out of a retrieved chunk
- Tempting wrong fix: Ship it; latency and cost both look excellent.
- Correct path: Route by difficulty instead of downgrading everything.
