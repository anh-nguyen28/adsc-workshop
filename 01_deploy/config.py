"""
╔══════════════════════════════════════════════════════════════════════════╗
║  THIS IS THE ONLY FILE YOU EDIT.                                         ║
║                                                                          ║
║  Change ONE lever, then re-run `make bench` and write down what moved.   ║
║  Fill the rungs on your decision sheet IN ORDER — you may not spend      ║
║  money on rung 5 until rungs 1-4 are filled in.                          ║
╚══════════════════════════════════════════════════════════════════════════╝

Everything here ships OFF or EXPENSIVE on purpose. That is the incident.
"""

# ─── RUNG 1 · CONFIRM THE BOTTLENECK ─────────────────────────────────────
# Nothing to change here. Run `make bench` and read two numbers off the
# report before you touch anything else:
#
#     queue wait p95   ← people standing in line
#     compute  p95     ← the model actually working
#
# Whichever is bigger tells you what kind of problem you have. Write it on
# the decision sheet. Teams that skip this step buy the wrong fix.


# ─── RUNG 2 · IMPROVE EFFICIENCY (free) ──────────────────────────────────

RESPONSE_CACHE = False
# Exact-match cache keyed on the fully assembled prompt. During finals week a
# lot of students ask the same question in the same words. A hit skips retrieval
# AND generation entirely, so it costs nothing at all.
#
# Note this is a RESPONSE cache -- it stores finished answers. That is a
# different thing from prompt caching below, and it is worth knowing which one
# people mean when they say "we added caching".

PREFIX_CACHE = False
# Prompt/prefix caching, the real thing. Every request re-reads the same system
# prompt block before it gets to your question. This computes the attention
# cache for that block ONCE and reuses it, so the model skips re-reading it.
#
# Unlike the response cache this does not skip generation -- you still pay for
# every output token. It discounts the repeated INPUT only. That is exactly how
# prompt caching works at every commercial provider, and why it matters that
# the static part of a prompt comes first and the varying part comes last.

SEMANTIC_CACHE = False
# Same idea, but matches questions that MEAN the same thing rather than ones
# spelled the same way. Reuses the embedding model retrieval already loaded,
# so it costs one extra vector comparison.
# Careful: a stale hit on a personalised or time-sensitive question is worse
# than a slow correct answer.

SEMANTIC_CACHE_THRESHOLD = 0.92
# Cosine similarity above which two questions count as "the same".
# Lower = more hits, more risk of answering the wrong question.


# ─── RUNG 3 · DO LESS WORK PER REQUEST ───────────────────────────────────

MAX_TOKENS = 32
# Hard cap on generated tokens. Latency is roughly linear in this number,
# and output tokens cost several times what input tokens cost.
# Ask yourself: does a study assistant actually need 96 tokens to answer?

SYSTEM_PROMPT = "LONG"
# "LONG"    — the 1,200-token instruction block Nimbus shipped with
# "TRIMMED" — the 180-token version that says the same thing
# Every request pays to re-read this. Nobody has ever audited it.

RETRIEVE_K = 4
# How many course-note chunks get stuffed into the prompt. More context is
# not free: it lands in the prefill on every single request.


# ─── RUNG 4 · REBALANCE ──────────────────────────────────────────────────

ROUTE_EASY = False
# Send easy questions (short, factual, definitional) to the small model and
# keep the large one for the hard ones. No training required — it is a
# heuristic. Most traffic is easier than the model you sized for.

MODEL_TIER = "large"
# "large" | "small"
#
# ⚠  Setting this to "small" sends EVERY request to the small model. It will
#    make your latency and cost numbers look fantastic.
#    Before you ship it, look at what the eval card says about quality.


# ─── RUNG 5 · ADD CAPACITY (this one costs money) ────────────────────────

MAX_CONCURRENT = 2
# How many requests are allowed to compute at once. Everything else waits in
# the queue — that wait is what `queue wait p95` measures.
#
# Raising this is NOT automatically a win. This box has a fixed number of
# cores; letting more requests in at once does not create more compute, it
# just moves the waiting from the queue into the model. Try it and look at
# what happens to p95 vs queue wait.

REPLICAS = 1
# Pretend replicas. Divides queue pressure, multiplies your bill.
# The only lever on this page that costs real money.


# ─── RUNG 6 · LOAD MANAGEMENT ────────────────────────────────────────────

SHED_ABOVE_QUEUE = None
# Set to an integer to reject requests with 429 + Retry-After once the queue
# is deeper than this. Failing fast and honestly beats timing out slowly —
# but every shed request is a student who did not get an answer.
