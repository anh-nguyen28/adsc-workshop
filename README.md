# Nimbus Is On Fire 🔥

**A 20-minute hands-on activity: deploy an AI study assistant, benchmark it, diagnose bottlenecks, and scale it until it meets SLOs.**

---

## Table of Contents

- [The Scenario](#the-scenario)
- [Core Lesson](#core-lesson)
- [System Architecture](#system-architecture)
- [Setup (5 min)](#setup-5-min)
- [Part 1: Deploy the Service (5 min)](#part-1-deploy-the-service-5-min)
- [Part 2: Measure & Optimize (10 min)](#part-2-measure--optimize-10-min)
- [The Optimization Ladder](#the-optimization-ladder)
- [Configuration Reference](#configuration-reference)
- [Project Structure](#project-structure)
- [FAQ & Troubleshooting](#faq--troubleshooting)

---

## The Scenario

**Nimbus** is an AI study assistant for university courses. It answers student questions by searching course notes and generating responses using a language model.

It went viral during finals week. Traffic surged 5x overnight. You are on call.

### Your Mission

Get the system back within SLOs **without breaking quality**:

| Metric | Target | Current |
| --- | --- | --- |
| **Latency** (p95) | ≤ 5.0 seconds | ❌ Failing |
| **Cost** | ≤ $1,500/month | ❌ Failing |
| **Quality** | ≥ 80% accuracy | ✓ Pre-measured |

---

## Core Lesson

> **Production engineering is a negotiation between latency, cost, and quality.**
>
> Everyone's first instinct when a system is slow is to buy bigger hardware or downgrade the model. Both are expensive. Both are usually wrong.
>
> This activity shows you how to measure before you spend—and why the cheapest fix is almost always a configuration change, not a bigger bill.

**You will not guess.** Every claim you make is backed by real measurements from your own laptop.

---

## System Architecture

### High-Level Flow

```
Request from student
    ↓
[Request Received] → (Shed if queue is too deep?)
    ↓
[Enqueue for Processing]
    ↓
[Queue Wait] ← This is latency you might measure here
    ↓
[Retrieve Relevant Course Notes] ← Cached? Response cache? Semantic cache?
    ↓
[Assemble Prompt] ← (System prompt + retrieval results + question)
    ↓
[Route to Model] ← (Small model or large model?)
    ↓
[Generate Response] ← Prefix cache saves re-reading system prompt
    ↓
[Compute Time] ← This is latency you measure here
    ↓
[Stream Response to Client]
    ↓
Response Complete
```

### Components

| Component | Purpose | Located In |
| --- | --- | --- |
| **Request Handler** | Receives requests, manages queue | `01_deploy/app.py` |
| **Retrieval Engine** | Searches course notes | `01_deploy/retrieval.py` |
| **Model Tier System** | Small (fast, cheap) or Large (slower, better quality) | `01_deploy/model.py` |
| **Caching Layer** | Response cache, prefix cache, semantic cache | `01_deploy/levers.py` |
| **Timing Instrument** | Measures queue wait vs. compute time separately | `01_deploy/timing.py` |
| **Benchmark Tool** | Simulates traffic with realistic concurrency | `02_benchmark/run.py` |
| **Metrics Analyzer** | Calculates latency percentiles, cost, PASS/FAIL | `02_benchmark/report.py` |

### Key Insight: Queue Wait vs. Compute Time

The system **separates queue wait from compute time** — this is critical for diagnosis:

- **High queue wait, low compute time** = You need more capacity (concurrency, replicas)
- **High compute time, low queue wait** = You need efficiency (caching, smaller models, less work)

Different problems → different solutions. Most teams guess wrong here; you'll measure and know.

---

## Setup (5 min)

### Option 1: GitHub Codespace (Recommended — nothing to install)

1. Click the green **Code** button at the top of the repo
2. Select **Codespaces** → **Create codespace**
3. Wait for the environment to load (~1 min)
4. Open a terminal and skip to [Part 1](#part-1-deploy-the-service-5-min)

### Option 2: Local Machine

**Requirements:**
- Python 3.10 or newer
- ~3 GB of free disk space
- ~5 minutes for initial setup

**Setup steps:**

```bash
# Navigate to the workshop directory
cd adsc-workshop

# Create virtual environment, install dependencies, download models
make setup

# This will:
# ✓ Create a Python virtual environment
# ✓ Install all dependencies (FastAPI, PyTorch, etc.)
# ✓ Build the course-note search index
# ✓ Download pre-trained model weights
```

⏱️ Takes ~3 minutes on a fast connection. On slower connections, the model download may take longer.

---

## Part 1: Deploy the Service (5 min)

### Start the server

In one terminal, run:

```bash
make serve
```

**Expected output:**
```
INFO:     Application startup complete
INFO:     Uvicorn running on http://127.0.0.1:8000
```

✓ **Nimbus is now live at `http://localhost:8000`**

### Verify it's working

In a new terminal, test a request:

```bash
curl -s http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"What is Big-O notation?"}' | python -m json.tool
```

You should get back a streaming JSON response with:
- The generated answer
- Queue wait time (in milliseconds)
- Compute time (in milliseconds)
- Tokens used

**Don't worry if the answer isn't perfect** — we're measuring the system, not the model's wisdom.

---

## Part 2: Measure & Optimize (10 min)

### Step 1: Measure the baseline (2 min)

In a third terminal, run the benchmark:

```bash
make bench
```

**What to expect:**
- The benchmark simulates 8 concurrent students asking questions
- Runs 16 questions total (~30 seconds)
- Produces a detailed report with latency percentiles and cost

**Read the report carefully:**

```
┌─────────────────────────────────────────────┐
│ LATENCY REPORT (milliseconds)               │
├─────────────────────────────────────────────┤
│ P50 (median)  : 2,500 ms                    │
│ P95           : 8,420 ms    ← You need <5s  │
│ P99           : 9,100 ms                    │
│
│ Queue wait p95  : 6,200 ms    ← People waiting
│ Compute p95     : 2,220 ms    ← Model working
├─────────────────────────────────────────────┤
│ COST: $3,200/month (target: $1,500)         │ ← Budget busted
│ PASS: ❌ FAIL                               │
└─────────────────────────────────────────────┘
```

**Key numbers to write down:**
- Queue wait p95: __________ ms
- Compute p95: __________ ms
- Monthly cost: $__________

**Diagnosis:** Which is bigger — queue wait or compute time? That tells you what kind of problem you have.

### Step 2-N: Optimize by changing ONE lever at a time

All tuning happens in **one file only**: `01_deploy/config.py`

1. **Open** `01_deploy/config.py`
2. **Change exactly ONE setting** (see the [Optimization Ladder](#the-optimization-ladder) below)
3. **Reload** the service (no restart needed):
   ```bash
   make reload
   ```
4. **Re-measure** to see the impact:
   ```bash
   make bench
   ```
5. **Record** what changed in the report
6. **Repeat** from step 2, changing one lever at a time

**Example workflow:**

```
[Baseline] Queue wait = 6,200 ms ← This is the problem
  ↓
Change: Set RESPONSE_CACHE = True
  ↓
make reload && make bench
  ↓
New Queue wait = 5,800 ms ← Got slightly better, but not enough
  ↓
Change: Set PREFIX_CACHE = True
  ↓
make reload && make bench
  ↓
New Queue wait = 3,200 ms ← Better! But still over 5 seconds
  ↓
Continue...
```

---

## The Optimization Ladder

**⚠️ IMPORTANT:** Follow these rungs IN ORDER. Do not skip ahead.

Why? Because jumping straight to rung 5 means you'll buy expensive hardware you didn't need. Skipping to "just use the small model" means you'll break quality without noticing.

### Rung 1: CONFIRM — Diagnose the bottleneck

**Action:** Run `make bench` and look at two numbers:
- `Queue wait p95`
- `Compute p95`

**Write down which one is bigger.** That tells you your actual problem.

**Levers:** None. Just measure.

---

### Rung 2: EFFICIENCY — Make repeated work free

These three caches let you skip expensive operations when you see the same question again (common during finals week).

#### 2a. Response Cache (`RESPONSE_CACHE`)

```python
RESPONSE_CACHE = True  # Set this
```

- **What it does:** Stores complete answers. If two students ask the exact same question, serve the cached answer instantly.
- **Cost of a hit:** Nothing at all (skips retrieval AND generation)
- **Tradeoff:** Only helps if students ask identical questions in identical wording
- **Impact on latency:** Eliminates entire request for cache hits

**When to enable:** Always safe to try first.

---

#### 2b. Prefix Cache (`PREFIX_CACHE`)

```python
PREFIX_CACHE = True  # Set this
```

- **What it does:** The system prompt (the instructions to the model) is the same for every request. Prefix caching computes the attention mechanism for it *once* and reuses it.
- **Cost of a hit:** Discounts the input tokens (the static part; output tokens still cost full price)
- **Tradeoff:** Requires the static prompt to come before the question in the prompt assembly
- **Impact on latency:** Saves time on model prefill for every request

**How it works:**
```
Request 1: "Explain Big-O notation"
  → Model reads 1,200-token system prompt + question
  → Saves attention cache

Request 2: "What is binary search?"
  → Model reuses cached attention for system prompt
  → Only processes 1,200-token question + this new question
  → 50-60% faster prefill
```

**When to enable:** Enables if compute time dominates.

---

#### 2c. Semantic Cache (`SEMANTIC_CACHE`)

```python
SEMANTIC_CACHE = True
SEMANTIC_CACHE_THRESHOLD = 0.92  # Cosine similarity threshold
```

- **What it does:** Matches questions that mean the same thing, even if worded differently
- **Cost of a hit:** Nothing (reuses the answer)
- **Cost of miss:** One extra embedding comparison per request
- **Tradeoff:** Risk of wrong answer if threshold too low (e.g., "When are office hours?" vs "Where can I find the instructor?")
- **Impact on latency:** Eliminates generation for cache hits

**Tuning:**
- `SEMANTIC_CACHE_THRESHOLD = 0.92` = Conservative (only very similar questions match)
- `SEMANTIC_CACHE_THRESHOLD = 0.80` = Aggressive (more hits, more risk)

**When to enable:** Enable if response cache seems too narrow (few hits).

---

### Rung 3: LESS WORK — Reduce work per request

These levers make each request cheaper by reducing tokens processed.

#### 3a. Limit Output Tokens (`MAX_TOKENS`)

```python
MAX_TOKENS = 32  # Default: 32
```

**Change to:** Start with 16 or even 8

- **What it does:** Hard cap on generated tokens
- **Cost of reduction:** Answers might be incomplete
- **Impact on latency:** Roughly linear — fewer tokens = proportionally faster
- **Impact on quality:** Shorter answers might lose nuance (will show in eval card)

**Tradeoff:** A study assistant can often answer in one sentence. Does it need 96 tokens?

---

#### 3b. Trim System Prompt (`SYSTEM_PROMPT`)

```python
SYSTEM_PROMPT = "LONG"  # 1,200 tokens
```

**Change to:** `SYSTEM_PROMPT = "TRIMMED"` (180 tokens)

- **What it does:** Uses a shorter version of the system instructions
- **Cost of reduction:** Potentially less accurate routing/formatting
- **Impact on latency:** Every request reads this; 1,000-token reduction helps prefill time
- **Impact on quality:** Usually minimal if trimmed carefully

**When to change:** If prefix cache is enabled, this saves on every hit.

---

#### 3c. Reduce Retrieved Context (`RETRIEVE_K`)

```python
RETRIEVE_K = 4  # Default: 4 retrieved chunks
```

**Change to:** 2 or 3

- **What it does:** How many course-note chunks to include in the prompt
- **Cost of reduction:** Less context for the model to search through
- **Impact on latency:** Smaller prompt = faster prefill
- **Impact on quality:** Less information might hurt answer quality

---

### Rung 4: REBALANCE — Route easy work to cheap models

Most traffic is easier than you think. Send easy questions to the small, fast, cheap model.

#### 4a. Enable Smart Routing (`ROUTE_EASY`)

```python
ROUTE_EASY = True
```

- **What it does:** Heuristically detects "easy" questions (short, factual, definitional) and routes them to the small model
- **Cost of reduction:** Small model costs 12x less per token
- **Impact on latency:** Small model is significantly faster
- **Impact on quality:** Small model scores ~67% on reasoning questions (see eval card)

**Heuristics for "easy":**
- Length of question < threshold
- Contains definitional keywords ("What is", "Define", "Explain")
- Retrieved context has a clear answer

---

#### 4b. Force Small Model (`MODEL_TIER`)

```python
MODEL_TIER = "small"  # Instead of "large"
```

**⚠️ WARNING:** This improves latency and cost dramatically, BUT the small model only achieves ~67% quality on reasoning questions.

- **Impact on latency:** ~3x faster
- **Impact on cost:** ~12x cheaper
- **Impact on quality:** Drops to ~67% (your eval card shows this)

**Why this is a trap:** Latency and cost numbers look fantastic. But the eval card shows you break quality without knowing it. This is why you have the measured numbers first.

---

### Rung 5: CAPACITY — Add compute resources (costs money)

Only enable these if rungs 1-4 didn't solve the problem.

#### 5a. Increase Concurrency (`MAX_CONCURRENT`)

```python
MAX_CONCURRENT = 2  # Default: 2
```

**Change to:** 4, 6, 8

- **What it does:** Allow more requests to compute simultaneously
- **Cost:** CPU pressure (this machine has a fixed number of cores)
- **Impact on latency:** Reduces queue wait BUT may increase individual request time (contention)
- **Impact on cost:** No direct cost (all on same machine)

**⚠️ Trap:** Raising MAX_CONCURRENT does not automatically help. More requests in flight = more contention for CPU. Test and measure.

**Hard limit:** MAX_CONCURRENT must be < benchmark concurrency, or nothing ever queues (and the exercise breaks).

---

#### 5b. Add Replicas (`REPLICAS`)

```python
REPLICAS = 1  # Default: 1
```

**Change to:** 2, 3, etc.

- **What it does:** Simulate having 2+ identical servers (in real deployment, these are separate $300/mo instances)
- **Cost:** $300/month per replica
- **Impact on latency:** Queue is split across replicas → queue wait drops dramatically
- **Impact on cost:** Direct cost increase

**When to enable:** Only after confirming you've exhausted rungs 1-4.

---

### Rung 6: LOAD MANAGEMENT — Fail honestly

#### 6a. Shed Overload (`SHED_ABOVE_QUEUE`)

```python
SHED_ABOVE_QUEUE = None  # Default: disabled
```

**Change to:** 20 (shed requests when queue > 20)

- **What it does:** Reject new requests with HTTP 429 + Retry-After when queue is deep
- **Cost:** Some students don't get answers
- **Benefit:** System stays responsive instead of having everyone timeout
- **Better than:** Timing out after 30 seconds of waiting

**When to enable:** Only as last resort for overload scenarios.

---

## Configuration Reference

Quick lookup of all tunable parameters in `01_deploy/config.py`:

```python
# ─── RUNG 2: CACHING (free efficiency) ────────────────────────
RESPONSE_CACHE = False              # Exact-match answer cache
PREFIX_CACHE = False                # Reuse model attention cache for system prompt
SEMANTIC_CACHE = False              # Fuzzy-match answer cache
SEMANTIC_CACHE_THRESHOLD = 0.92     # Cosine similarity (0.80 = loose, 0.92 = strict)

# ─── RUNG 3: REDUCE WORK ─────────────────────────────────────
MAX_TOKENS = 32                     # Output token limit (latency is linear in this)
SYSTEM_PROMPT = "LONG"              # "LONG" (1,200) or "TRIMMED" (180)
RETRIEVE_K = 4                      # Chunks of context to include

# ─── RUNG 4: REBALANCE ────────────────────────────────────────
ROUTE_EASY = False                  # Smart routing to small model
MODEL_TIER = "large"                # "large" or "small"

# ─── RUNG 5: CAPACITY (costs money) ──────────────────────────
MAX_CONCURRENT = 2                  # Requests computing in parallel
REPLICAS = 1                        # Simulated replicas ($300/mo each)

# ─── RUNG 6: LOAD MANAGEMENT ─────────────────────────────────
SHED_ABOVE_QUEUE = None             # Reject 429 if queue > N
```

---

## Making Changes: The Workflow

**Every time you change `config.py`:**

1. **Reload** (no restart needed):
   ```bash
   make reload
   ```
   
   Expected output:
   ```json
   {"status": "config reloaded", "queue_depth": 0, "caches_cleared": true}
   ```

2. **Immediately** run benchmark in another terminal:
   ```bash
   make bench
   ```

3. **Compare** to previous numbers. Write down:
   - New p95 latency
   - New cost
   - New quality (stays the same unless you changed model tiers)

4. **Decide** whether to keep the change or try something else

---

## Project Structure

```
adsc-workshop/                           ← You are here
│
├── README.md                            ← This file
├── participant-preflight.md             ← Run before session (downloads models)
├── Makefile                             ← make setup, make serve, make bench, make reload
├── requirements.txt                     ← All dependencies (locked versions)
├── scenario.json                        ← SLO targets (READ-ONLY)
│
├── 01_deploy/                           ← THE SERVICE (Part 1)
│   ├── README.md                        ← Detailed deploy instructions
│   ├── config.py                        ⭐ THE ONLY FILE YOU EDIT
│   ├── app.py                           ← Request handler, streaming, queue logic
│   ├── model.py                         ← Two model tiers (small & large)
│   ├── retrieval.py                     ← Search course notes
│   ├── levers.py                        ← Caching, routing, prompt assembly
│   └── timing.py                        ← Measure queue wait vs. compute time
│
├── 02_benchmark/                        ← THE INSTRUMENT (Part 2)
│   ├── README.md                        ← How to interpret results
│   ├── run.py                           ← Load generator (realistic traffic)
│   ├── report.py                        ← Latency percentiles, cost, PASS/FAIL
│   ├── prompts.jsonl                    ← 100 pre-generated questions
│   └── paper_track.md                   ← Fallback if laptop fails
│
├── data/                                ← Course notes database
│   ├── notes.json                       ← Raw course content
│   ├── index.npz                        ← Pre-built search index
│   └── build_index.py                   ← Regenerate index (rarely needed)
│
├── results/                             ← Your benchmark results
│   └── *.json                           ← One JSON file per run (auto-generated)
│
└── facilitators/                        ← Facilitator-only tools (ignore for now)
    ├── calibrate.py                     ← Re-measure SLO on your hardware
    ├── eval.py                          ← Quality evaluation
    ├── eval_card.md                     ← Pre-computed quality results
    └── answer_key.md                    ← Correct answers to eval questions
```

---

## Common Commands Cheat Sheet

### Setup & Running

```bash
# First time: create venv, install deps, download models (~3 min)
make setup

# Start the service (one terminal)
make serve

# Run benchmark (another terminal)
make bench

# Reload config without restarting (~2 sec)
make reload

# Check current config on running server
make metrics

# Clean up old benchmark results
make clean
```

### Benchmark with Options

```bash
# Default: 16 requests, rate=4/sec, concurrency=8
make bench

# Custom: fewer requests (faster, noisier percentiles)
make bench ARGS="--requests 8"

# Custom: higher concurrency
make bench ARGS="--concurrency 16"

# Custom: label your run for results tracking
make bench ARGS="--label 'prefix cache on'"

# Combine options
make bench ARGS="--requests 32 --concurrency 12 --label 'iteration 3'"
```

### Debugging

```bash
# Test the service manually
curl http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"What is Big-O?"}'

# Get raw metrics from running server
make metrics

# See last benchmark result
cat results/*.json | tail -1 | python -m json.tool
```

---

## FAQ & Troubleshooting

### "make setup" hangs or fails

**Symptom:** Stuck on "Downloading model weights"

**Cause:** Model files are large (~1-2 GB). Slow internet connection.

**Fix:**
```bash
# Try with explicit timeout and retries
make setup

# If still stuck after 10 min, Ctrl+C and retry
# Models are cached, so re-running is faster
```

---

### Service won't start ("Address already in use")

**Symptom:** 
```
ERROR: Address 127.0.0.1:8000 is already in use
```

**Cause:** A previous `make serve` is still running, or something else is on port 8000.

**Fix:**
```bash
# Kill the old process
lsof -i :8000 | grep LISTEN | awk '{print $2}' | xargs kill -9

# Try make serve again
make serve

# Or use a different port
make serve PORT=8001
```

---

### Benchmark shows "0 successful requests"

**Symptom:**
```
Successful requests: 0 / 16
```

**Cause:** Service is not running, or not reachable.

**Fix:**
```bash
# Verify service is running
curl http://localhost:8000/metrics

# If curl fails, restart the service
# In the service terminal: Ctrl+C, then: make serve
```

---

### "make reload" fails

**Symptom:**
```
curl: (7) Failed to connect
```

**Cause:** Service crashed or isn't listening.

**Fix:**
```bash
# Restart the service
# In service terminal: Ctrl+C
make serve
```

---

### Config change doesn't seem to take effect

**Symptom:** You change `config.py` but benchmark shows same latency.

**Cause:** You didn't run `make reload`.

**Fix:**
```bash
# ALWAYS reload after config changes
make reload

# Wait for response (should see JSON success message)
# Then run benchmark
make bench
```

---

### Model quality seems bad

**Symptom:** "The AI answers don't make sense."

**Cause:** This is expected! These are tiny models (135M-360M parameters) running on CPU.

**This is intentional:** We're measuring the *system*, not judging the model. Latency and queueing work the same whether the model has 135M or 405B parameters.

Quality is measured separately (see `facilitators/eval_card.md`).

---

### "Percentiles are degenerate" warning

**Symptom:**
```
WARNING: Only 16 requests, percentiles are degenerate
P90 and P95 show same value, P99 is just the max
```

**Cause:** 16 requests is small for statistical significance.

**Fix:** Use more requests for final measurements:
```bash
make bench ARGS="--requests 64"
```

But for iteration, 16 is fast enough to validate a change.

---

### Codespace tips

**Expose port publicly (for sharing results):**
```bash
make public
```
This gives you a public URL instead of localhost.

**Model download is slow on Codespace:**
- Codespace has slower internet than most laptops
- Run `make setup` once and be patient
- Subsequent runs are much faster (models cached)

---

## What Happens Next (After the Activity)

Once you pass the SLOs:

1. **Real production deployment** would replace the simulated `REPLICAS` lever with actual servers
2. **Real caching** (Redis, etc.) would replace the in-memory caches
3. **Real load** would come from actual student requests instead of the benchmark
4. **Real costs** would account for infrastructure, not just model inference

But the *principle* stays the same: **measure, diagnose, change one thing, measure again.**

---

## Further Reading

- [`01_deploy/README.md`](01_deploy/README.md) — Service internals
- [`02_benchmark/README.md`](02_benchmark/README.md) — Understanding benchmark reports
- `presentation-core-ideas.md` — The talk this activity supports
- `CLAUDE.md` — Project design principles & invariants
