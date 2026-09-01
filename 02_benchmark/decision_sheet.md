# Decision Sheet — fill this in as you go

Team: ______________________  Table: ______

**Rule: fill the rungs in order. You may not use rung 5 until rungs 1–4 are done.**

---

## Rung 1 — CONFIRM the bottleneck

Run `make bench` with nothing changed. Copy the numbers:

| | value |
| --- | --- |
| p95 latency | ________ s |
| queue wait p95 | ________ s |
| compute p95 | ________ s |
| cost | $________ /month |

**Which is bigger, queue wait or compute?** ________________

**So what kind of problem is this?** (one sentence, in your own words)

> ______________________________________________________________

---

## Rung 2 — EFFICIENCY (free)

Lever(s) changed: ______________________________

| p95 | queue wait | compute | cache hit rate | $/month |
| --- | --- | --- | --- | --- |
| ____ s | ____ s | ____ s | ____ % | $____ |

What moved, and why do you think it moved?

> ______________________________________________________________

---

## Rung 3 — DO LESS WORK PER REQUEST

Lever(s) changed: ______________________________

| p95 | queue wait | compute | cache hit rate | $/month |
| --- | --- | --- | --- | --- |
| ____ s | ____ s | ____ s | ____ % | $____ |

> ______________________________________________________________

---

## Rung 4 — REBALANCE

Lever(s) changed: ______________________________

| p95 | queue wait | compute | cache hit rate | $/month |
| --- | --- | --- | --- | --- |
| ____ s | ____ s | ____ s | ____ % | $____ |

> ______________________________________________________________

---

## Rung 5 — ADD CAPACITY  ⚠ this one costs money

Only fill this in if rungs 1–4 are complete and you are still failing.

Lever(s) changed: ______________________________

| p95 | queue wait | compute | cache hit rate | $/month |
| --- | --- | --- | --- | --- |
| ____ s | ____ s | ____ s | ____ % | $____ |

Was it necessary? Could you have got there without it?

> ______________________________________________________________

---

## Rung 6 — LOAD MANAGEMENT / QUALITY CHECK

Lever(s) changed: ______________________________

Requests shed: ________

**Before you would ship this, what would you check?** Look at the eval card.

> ______________________________________________________________

---

## Final answer

**Ordered list of moves we made:**

1. ____________________________________________
2. ____________________________________________
3. ____________________________________________
4. ____________________________________________
5. ____________________________________________

**Final p95:** ________ s   **Final cost:** $________ /month
**Constraints met:** ____ / 2

**The one thing we would verify before shipping this:**

> ______________________________________________________________

---

### Did you reach for `MODEL_TIER = "small"`?

Many teams do, usually in the first two minutes. It is a real option and it is
on the menu on purpose.

If you used it — what does the eval card say about it, and would you still ship it?

> ______________________________________________________________
