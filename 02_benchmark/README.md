# Part 3 — Benchmark it, then scale it

Goal: find out what is actually wrong, fix it in the right order, and prove the
fix with numbers.

---

## 1. Measure

With `make serve` running in another terminal:

```bash
make bench
```

You will get a report like this:

```
NIMBUS BENCHMARK - run 1  baseline
====================================================================
requests     16 ok · 0 shed · 0 failed      duration  45.1 s
throughput   0.4 req/s · 9 output tok/s

latency      p50    19.66 s
             p95    25.36 s   SLO 5.00 s   FAIL
             p99    25.61 s
TTFT         p95    22.56 s

             ── where the time went ──
queue wait   p95    19.59 s   <- waiting in line
compute      p95     7.38 s   <- actually working
cache        hit rate 0%

cost         $0.541 / 1k requests
             $2,434 / month @ 150,000/day   budget $1,500   FAIL

--------------------------------------------------------------------
VERDICT  0/2 constraints met
hint     queue wait exceeds compute. The model is not your problem.
```

**Read those two lines under "where the time went" before you touch anything.**
They are the whole diagnosis:

- **queue wait high** → too many requests, not enough being let through. Making
  the model faster barely helps; you need each request to *finish sooner* so the
  next one can start, or you need to let more through at once.
- **compute high** → each individual request is doing too much work. Look at how
  many tokens are going in and coming out.

Write your answer down before you change anything. Teams that skip this step buy
the wrong fix.

### Benchmarking a Cloud Run service

Participants do not need to clone the repository: they can use the participant
page at the Cloud Run URL. A facilitator can benchmark that same URL from a
prepared checkout:

```bash
export NIMBUS_URL='https://...run.app'
export NIMBUS_ADMIN_TOKEN='the-value-from-secret-manager'
make bench URL="$NIMBUS_URL"
```

The token is used only to read protected `/metrics`; it is not sent to student
`/ask` requests and is not written to `results/run-N.json`. Use `make reload`
only when deliberately changing the deployed configuration, because it clears
the service's in-memory caches.

---

## 2. Climb the ladder — in order

Open `01_deploy/config.py`. Change **one** lever. Then:

```bash
make reload    # picks up config.py without restarting (~instant)
make bench     # did the number move?
```

Write down what moved before you change anything else. Rung 2 lists three
levers; turn them on **one at a time**. They do different things, and if you
flip all three at once you will not know which one earned the improvement.

| Rung | Move | Levers |
| --- | --- | --- |
| **1** | **Confirm** the bottleneck | none — just read the report |
| **2** | **Make repeated work free** | `RESPONSE_CACHE`, `PREFIX_CACHE`, `SEMANTIC_CACHE` |
| **3** | **Do less per request** | `MAX_TOKENS`, `SYSTEM_PROMPT`, `RETRIEVE_K` |
| **4** | **Send easy work to the cheap path** | `ROUTE_EASY` |
| **5** | **Buy capacity** | `MAX_CONCURRENT` (local), `REPLICAS` (local simulation); Cloud Run uses max instances |
| **6** | **Fail honestly when overloaded** | `SHED_ABOVE_QUEUE` |

**You may not use rung 5 until rungs 1–4 are filled in on your decision sheet.**
That constraint is the entire point of the exercise. Capacity is the fix that
always works and always costs money; it should be the last thing you reach for,
not the first.

### The one that looks like a free win

`MODEL_TIER = "small"` sends every request to the small model. Your latency and
cost numbers will look fantastic.

Before you ship it, check the eval card. Then decide whether you would put your
name on it.

---

## 3. Compare

Every run is saved to `results/run-N.json`, and each report shows the previous
run's headline numbers so you can see what your change actually did.

```bash
make bench ARGS="--label 'cache on'"      # label your runs, you will forget
make bench ARGS="--requests 32"           # more samples, steadier p95, slower run
make bench ARGS="--concurrency 16"        # heavier load
```

### Two kinds of caching, and they are not the same thing

`RESPONSE_CACHE` stores finished answers. A hit skips retrieval and generation
entirely and costs nothing at all.

`PREFIX_CACHE` is prompt caching, the thing providers sell. It computes the
attention cache for the static part of the prompt once and reuses it, so the
model stops re-reading your system prompt on every request. It does **not** skip
generation — you still pay for every output token. It discounts repeated *input*.

That distinction is why `build_prompt` puts the static block first and your
question last: a prefix cache only helps up to the first byte that changes. One
production team moved a single dynamic ID from the middle of their prompt to the
end, took their hit rate from 7% to 74%, and cut their bill 59%. Same prompt,
different order.

---

## How the benchmark works

`run.py` is plain `asyncio` + `httpx`, about 150 lines, deliberately short
enough to read. If you are going to trust a number, you should be able to see
where it came from.

**1 · A frozen question corpus.** `prompts.jsonl` holds 60 realistic student
questions, of which 21 are distinct. The duplicates are deliberate — during
finals week a lot of people ask the same thing in the same words, and a few ask
it in different words. That mix is what gives the cache levers something real to
hit, and it makes your hit rate reproducible instead of luck.

**2 · Warm-up requests are discarded.** First-call overhead is real but it is not
what you are measuring.

**3 · Poisson arrivals, not a thundering herd.** `--rate` controls how fast
requests *arrive*; `--concurrency` separately caps how many are in flight. Real
traffic arrives at a rate — it does not all show up at the same instant. A load
generator that fires everything simultaneously reports a TTFT no user would ever
experience.

**4 · Every request is timed individually**, off the streamed response:

| Metric | Where it comes from |
| --- | --- |
| **TTFT** | first streamed chunk minus send time |
| **end-to-end latency** | last chunk minus send time |
| **inter-token latency** | the gaps between chunks |
| **queue wait / compute** | the server reports its own split in the final event |
| **tokens in / out** | the final event; cloud providers may mark usage as unreported |
| **cache hit, model tier** | the final event |

**5 · Percentiles, not averages.** p50/p90/p95/p99. An average hides the tail,
and the tail is what users actually feel and what pages you at 2am.

> **Be careful with this number.** With 16 requests, "p95" is literally the
> second-slowest request — and "p99" would be the slowest, which is why the
> report prints `slowest` instead of pretending otherwise. Repeat runs of an
> identical config vary by about 12% on this workload, so the report marks any
> result within 15% of the line as **MARGINAL** and tells you to run it again.
> Use `--requests 32` when you want to trust a close call.

**6 · Cost comes from measured tokens**, priced with the rates in
`scenario.json`, projected over the scenario's monthly request volume. For
Cloud Run, model tokens and Cloud Run infrastructure are separate. If a
streaming provider does not return usage, the report shows `UNKNOWN` rather
than pricing zero tokens.

**7 · A verdict, not just numbers.** The report says PASS or FAIL against the
stated SLO and budget. A benchmark that only prints numbers is a measurement
tool; one with a win condition is something you can actually play.
