"""Generate the paper track from measurement. NOT FOR PARTICIPANTS.

The paper track is what a table uses when their laptop, the wifi or the cloud
project lets them down, and it is not a consolation prize: a fixed printed panel
is arguably the BEST medium for pattern-matching a signature, because the whole
skill being taught is reading one.

It is generated rather than written for the same reason the eval card and the
answer key are. A hand-written panel drifts from what the service actually does,
and a table would then be diagnosing a fiction.

    .venv/bin/python facilitators/calibrate_incidents.py   # produces the panels
    .venv/bin/python facilitators/make_paper_track.py
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "facilitators"))

from incidents import INCIDENTS  # noqa: E402

PANELS = ROOT / "facilitators" / "incident_panels"
SIGS = ROOT / "facilitators" / "signatures.json"
OUT = ROOT / "02_benchmark" / "paper_track.md"


def main() -> None:
    if not SIGS.exists() or not PANELS.exists():
        sys.exit("Run facilitators/calibrate_incidents.py first.")
    meta = json.loads(SIGS.read_text())
    scenario = json.loads((ROOT / "scenario.json").read_text())
    c = scenario["constraints"]

    order = [n for n in INCIDENTS if (PANELS / f"{n}.txt").exists()]
    if not order:
        sys.exit("No measured panels found.")

    L = [
        "# Nimbus paper track — no laptop required",
        "",
        "Use this if your table cannot reach the service. You make the same",
        "diagnosis the coding track makes, from the same panel it would print.",
        "",
        f"> **Generated from measurement** on the `{meta['backend']}` backend at "
        f"{meta['measured_at']}. Latency is hardware-dependent; token counts and",
        "> shares are not. Regenerate with `facilitators/calibrate_incidents.py`",
        "> followed by `facilitators/make_paper_track.py`.",
        "",
        "## Your targets",
        "",
        "| Constraint | Target |",
        "| --- | ---: |",
        f"| p95 latency | at most {c['slo_p95_latency_s']:.1f} s |",
        f"| Monthly cost | at most ${c['budget_usd_per_month']:,} |",
        f"| Eval quality | at least {c['quality_bar_eval_pct']}% |",
        "",
        "## How to use this",
        "",
        "For each incident below: read the panel, decide **where the time went**,",
        "then decide **what you would change**. Write both down before turning to",
        "the facilitator's answer. The panel names the biggest contributor; it",
        "deliberately does not name the fix.",
        "",
        "---",
        "",
    ]

    for name in order:
        spec = INCIDENTS[name]
        L += [
            f"## {spec['title']}",
            "",
            f"**What was reported.** {spec['public_symptom']}",
            "",
            f"**Who it affects.** {spec['user_impact']}",
            "",
            "```text",
            (PANELS / f"{name}.txt").read_text().strip(),
            "```",
            "",
            "1. Which row is the largest contributor, and what is at baseline?",
            "2. Is the model implicated? Which number settles it?",
            "3. What is the one change you would make first?",
            "",
            "---",
            "",
        ]

    L += [
        "## Facilitator answers",
        "",
        "*Fold this section back, or print the pages above on their own.*",
        "",
    ]
    for name in order:
        spec = INCIDENTS[name]
        L += [
            f"**{spec['title']}** — {spec['private_truth']}",
            "",
            f"- Tell: {spec['discriminator']}",
            f"- Tempting wrong fix: {spec['tempting_wrong_fix']}",
            f"- Correct path: {spec['correct_path']}",
            "",
        ]

    OUT.write_text("\n".join(L))
    print(f"wrote {OUT.relative_to(ROOT)} ({len(order)} measured panels)")


if __name__ == "__main__":
    main()
