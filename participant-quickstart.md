# You are on call

Nimbus is a study assistant your university runs. Something is wrong with it.
Your job is to find out **what**, prove it with a measurement, fix it, and prove
the fix worked — in twenty minutes.

You need a browser. Nothing is installed on your laptop.

---

## Setup — about a minute

Open **[Cloud Shell](https://shell.cloud.google.com)** and paste this:

```bash
git clone https://github.com/YOUR-ORG/adsc-workshop.git
cd adsc-workshop
pip3 install --quiet httpx
export PATH="$PWD/cli:$PATH"
```

Then point it at your team's service. Your facilitator gives you both values:

```bash
nimbus init https://nimbus-team-X-r1-XXXXX.run.app YOUR-TEAM-TOKEN
```

---

## The loop

```bash
nimbus brief          # what was reported, and the targets you have to hit
nimbus baseline       # measure. change nothing yet.
nimbus diagnose       # read it back, with the questions worth asking
nimbus hypothesis ... # say what you think is wrong, and why
nimbus set KEY=VALUE  # change ONE thing
nimbus bench          # measure again
```

**`nimbus set` will refuse you until you have recorded a diagnosis.** That is on
purpose. Changing settings until something goes green teaches nothing, and you
will not be able to say afterwards which change did the work.

---

## Reading the report

The important block is this one:

```
             ── where the time went (p95, additive) ──
  client + network     0.06 s   ▏
  app queue wait       0.00 s   ▏
  retrieve             1.25 s   ████████████████████████
  generate             0.68 s   █████████████
                     --------
  sum of rows          1.99 s
```

Those rows **add up to the whole request**. Whatever is largest is where your
latency actually is — and, just as usefully, whatever is small is a thing you
can rule out. A request can be slow because it waited, because it fetched, or
because the model generated. Those are different problems with different fixes,
and they look identical from outside.

Two more numbers worth knowing:

- **input / output tokens** against their baseline. A request doing more work
  than it should shows up here, not in the clock.
- **provider retries.** A request that succeeded on its third attempt is slow
  for a reason no stage timer will show you.

The report names the biggest contributor. It will not tell you what to do about
it. That part is yours.

---

## The settings you can change

| setting | what it does |
| --- | --- |
| `RESPONSE_CACHE` | reuse a finished answer for an identical question |
| `SEMANTIC_CACHE` | reuse an answer for a question that *means* the same thing |
| `SEMANTIC_CACHE_THRESHOLD` | how similar counts as "the same" (0–1) |
| `MAX_TOKENS` | cap on how much the model generates |
| `SYSTEM_PROMPT` | `LONG`, `TRIMMED` or `VERBOSE` |
| `RETRIEVE_K` | how many course-note chunks go into the prompt |
| `ROUTE_EASY` | send easy questions to the cheaper model |
| `MODEL_TIER` | `large` or `small` — every request to one model |
| `MAX_CONCURRENT` | how many requests may reach the model at once |
| `SHED_ABOVE_QUEUE` | start refusing requests once the queue is deeper than this |

Change **one at a time**. Two at once tells you something helped, but not which.

---

## Before you say you are done

You have three targets, and the benchmark only checks two of them. It measures
latency and it prices the tokens. It cannot see whether the answers are any
good — and there is at least one change on that list which makes both numbers
look excellent by making the assistant worse.

Ask your facilitator for the eval card before you ship.
