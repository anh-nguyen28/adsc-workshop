# Facilitator Run Sheet — "Nimbus Is On Fire"

**Not for participants.**

20 minutes. One Incident Commander at the front, one facilitator per ~3 tables.

---

## Before the room opens

- [ ] Repo link + Codespaces badge sent 2–3 days ahead, with the glossary
- [ ] Someone has done a cold-account run start to finish this week
- [ ] Timer visible on the main screen
- [ ] Printed per table: incident brief, decision sheet, eval card
- [ ] A spare laptop per 3 tables, already set up
- [ ] `facilitators/answer_key.md` open on your phone, not on the projector

---

## Minute by minute

| Time | Phase | Incident Commander |
| --- | --- | --- |
| 0:00 | **The pager** | Read the incident brief aloud. "SLO is p95 under 5 seconds. Budget is $1,500 a month. Right now you are failing both." Tell them to start Codespaces **now** — it builds while you talk. |
| 2:00 | **Deploy** | "`make serve`. When it says Nimbus ready, you have a running service." Facilitators sweep for anyone stuck. |
| 4:00 | **Measure** | "`make bench`. Do not change anything yet." Wait for the room to get their FAIL. |
| 6:00 | **Rung 1** | **The critical beat.** "Before anyone touches config — look at queue wait versus compute. Which is bigger? Write it down." Do not let the room move on until tables have said it out loud. |
| 8:00 | **Climb** | Tables work the ladder. Facilitators circulate and enforce rung order. |
| 15:00 | **Poll** | "Hands up: who is passing both? Who got there without touching MAX_CONCURRENT or REPLICAS?" Put the split on the board. |
| 16:00 | **Share** | Pick one cheap table and one spendy table. 45 seconds each, numbers only. |
| 17:00 | **Reveal** | The ladder, the trap, the real companies, the closing line. |

**The reveal is protected. If you are behind, cut the share-out — never the reveal.**

---

## What facilitators actually say

| You see | You say |
| --- | --- |
| Jumping straight to `MAX_CONCURRENT` / `REPLICAS` | "Before you spend — which number tells you capacity is the problem? Show me." |
| Staring at the report, stuck | "What is the cheapest thing on that list that could possibly help? Start there." |
| Setting `MODEL_TIER = "small"` immediately | "Great — that will work. Now go look at the eval card and tell me if you would ship it." |
| Changing three levers at once | "Change one. Otherwise you will not know which one worked." |
| Done early | "Traffic just doubled. Run it with `--concurrency 16`. Does your fix still hold?" |
| Arguing about what to do | "Stop. What is your current p95? What is the single next move?" |

---

## The two things that must land

1. **Diagnosis before spending.** Queue wait ≫ compute means the model was never
   the problem. Teams that read that first solved it for free.
2. **The trap.** `MODEL_TIER = "small"` makes both numbers beautiful and puts
   quality under the bar. It is on the menu on purpose. It is not a wrong answer
   to shut down — it is the teaching moment, and it belongs in the reveal.

---

## Closing line

> **Scaling is diagnosis first. The cheapest fix is usually a config change —
> not a bigger bill, and not a worse model.**

---

## If something breaks

See `failure_playbook.md`. Short version: the paper track is complete. A table
with no working laptop can do every rung from the decision sheet and the eval
card alone, and their answers will be just as good.
