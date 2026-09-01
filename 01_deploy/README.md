# Part 2 — Deploy Nimbus

Goal: get Nimbus running, reachable, and answering questions. Five minutes.

---

## 1. Set up (once)

```bash
make setup
```

This creates a virtualenv, installs the pinned dependencies from
`requirements.txt`, and builds the course-note index. If you are in Codespaces
this has already happened for you.

## 2. Start it

```bash
make serve
```

You should see:

```
Nimbus ready | 48 note chunks | tier=large concurrency=2x1 max_tokens=32
INFO:     Uvicorn running on http://0.0.0.0:8000
```

The first start takes a few seconds because **both model tiers load before the
server accepts traffic**. That is deliberate — see "Why it is built this way"
below.

## 3. Ask it something

In a second terminal:

```bash
curl -N -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"What does the learning rate do?"}'
```

You get a stream of text, and then a final event with the numbers that matter:

```json
{"stats": {"queue_wait_ms": 0.0, "compute_ms": 4584.9,
           "stages_ms": {"retrieve": 193.7, "generate": 4383.9},
           "tokens_in": 772, "tokens_out": 39,
           "cache": "miss", "tier": "large"}}
```

## 4. Put it on the internet (optional, Codespaces only)

```bash
make public
```

This makes port 8000 publicly reachable and prints a URL like
`https://<you>-8000.app.github.dev`. Anyone can call it. Your service is live.

> If your organisation blocks public port forwarding, skip this. Nothing else
> in the activity depends on it.

---

## Why it is built this way

**Models load once, at startup, never inside a request handler.** Loading a
model per request is the most common LLM deployment mistake there is. Here it
would also make every number you measure meaningless.

**Nimbus retrieves before it generates.** It is a small RAG service, not a bare
chat wrapper:

```
request -> [shed?] -> [queue] -> [cache] -> [retrieve] -> [generate] -> done
           |__________________|            |_________________________|
                 QUEUE WAIT                        COMPUTE
```

That split matters more than anything else in this repo. **An overloaded queue
and a slow model look identical from the outside and have opposite fixes.** If
you cannot see them separately, you cannot diagnose anything — you can only
guess and spend money.

**Retrieval is one numpy dot product**, not a vector database. The index is 48
chunks of 384 floats — well under a megabyte. A vector DB here would add a
service to run, a port to bind and a new way for this to fail on the day, in
exchange for nothing.

**Responses stream.** Without a first-chunk timestamp there is no TTFT, and TTFT
is half of what the benchmark measures.

---

## The file you edit

Everything else in this folder is infrastructure you can read but should not
change. **`config.py` is the only file you edit.**

It ships with every lever off or expensive. That is the incident.

```
config.py       ★ the levers — this is your control panel
app.py            the service: request path, timing, streaming
model.py          the two model tiers (small 135M, large 360M)
retrieval.py      course-note search
levers.py         caches, router, the long vs trimmed system prompt
timing.py         the queue-wait / compute stopwatch
```

Open `config.py` now and read it. Do not change anything yet — go and measure
first. **Part 3 is where you find out what is actually wrong.**

---

## Useful commands

```bash
make metrics          # what config is the running server actually using?
make reload           # apply your config.py edit and clear answer caches
make serve PORT=8080  # run on a different port
```

After every change to `config.py`, run `make reload`, then run the benchmark
again. Reloading keeps the models warm and clears response caches, so each
configuration is measured fairly. If reload fails, stop `make serve` with
Ctrl-C and start it again.
