"""Confirm a deployed Nimbus is actually usable. NOT FOR PARTICIPANTS.

Run this after deploying and before handing out URLs. It checks the things that
have actually gone wrong on this project, in the order they went wrong:

  1. the service is serving traffic at all
  2. /health reports ready, on the expected backend, with the note index built
  3. the model it will call is the one you meant -- a service configured with a
     model the project cannot reach starts up HEALTHY and 404s every request,
     because warm() validates credentials, not model access
  4. a real question returns real text -- Gemini 2.5 spends the output budget
     thinking before answering, and at a low MAX_TOKENS returns NO text at all
     while latency and cost still look fine
  5. both tiers work -- one thinking budget across two models is not always
     valid for both, and an out-of-range value is a hard 400 on the tier a team
     reaches for as their fix
  6. the incident is not readable from any participant-facing endpoint

Usage:
    python facilitators/preflight.py --url https://...run.app
    python facilitators/preflight.py --all-services        # every nimbus-team-*
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

TIMEOUT = 120


def _get(url, token=None):
    req = urllib.request.Request(url, headers={"X-Nimbus-Admin-Token": token} if token else {})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())


def _ask(url, question, max_tokens=None):
    body = {"question": question}
    if max_tokens:
        body["max_tokens"] = max_tokens
    req = urllib.request.Request(f"{url}/ask", method="POST",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    text, stats, error = [], None, None
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        for raw in r:
            line = raw.decode(errors="replace").strip()
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if "delta" in event:
                text.append(event["delta"])
            elif "stats" in event:
                stats = event["stats"]
            elif "error" in event:
                error = event["error"]
    return "".join(text), stats, error


def check(url: str, token: str) -> list[str]:
    """Return a list of problems. Empty means good to hand out."""
    problems = []

    try:
        health = _get(f"{url}/health")
    except Exception as exc:  # noqa: BLE001
        return [f"/health unreachable: {exc}"]
    if not health.get("ok"):
        problems.append(f"/health not ok: {health}")
    if health.get("status") != "ready":
        problems.append(f"status is {health.get('status')!r}, not ready")
    if not health.get("note_chunks"):
        problems.append("no note chunks -- the retrieval index did not build")
    print(f"    health      ready · backend={health.get('backend')} · "
          f"{health.get('note_chunks')} note chunks")

    runtime = {}
    if token:
        try:
            metrics = _get(f"{url}/metrics", token)
            runtime = metrics.get("runtime", {})
            config = metrics.get("config", {})
            print(f"    models      large={runtime.get('model_large')} "
                  f"small={runtime.get('model_small')} "
                  f"thinking={runtime.get('thinking_budget')}")
            leaked = [k for k in config if "INCIDENT" in k.upper()]
            if leaked:
                problems.append(f"the incident is readable from /metrics: {leaked}")
        except urllib.error.HTTPError as exc:
            problems.append(f"/metrics returned {exc.code} -- wrong team token?")

    for tier_name, force in (("large", None), ("small", "small")):
        label = runtime.get(f"model_{tier_name}", tier_name)
        try:
            if force:
                # Reach the small tier the way a participant would: switch the
                # lever, ask, switch back.
                if not token:
                    print(f"    {tier_name:<11} skipped (needs the team token)")
                    continue
                _post_levers(url, token, {"MODEL_TIER": "small"})
            text, stats, error = _ask(url, "What is Big-O notation?")
            if error:
                problems.append(f"{tier_name} tier ({label}) failed: "
                                f"{error.get('message', error)}")
            elif not text.strip():
                problems.append(f"{tier_name} tier ({label}) returned NO TEXT -- "
                                f"thinking is probably consuming the whole "
                                f"output budget")
            else:
                print(f"    {tier_name:<11} {stats.get('model')} -> "
                      f"{text.strip()[:44]!r}")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{tier_name} tier ({label}) raised: {exc}")
        finally:
            if force and token:
                _post_levers(url, token, {"MODEL_TIER": "large"})

    return problems


def _post_levers(url, token, values):
    req = urllib.request.Request(f"{url}/levers", method="POST",
                                 data=json.dumps(values).encode(),
                                 headers={"Content-Type": "application/json",
                                          "X-Nimbus-Admin-Token": token})
    try:
        urllib.request.urlopen(req, timeout=TIMEOUT).read()
    except urllib.error.HTTPError as exc:
        if exc.code == 409:      # the diagnose-first gate; not a preflight failure
            return
        raise


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", help="one service URL")
    ap.add_argument("--all-services", action="store_true",
                    help="check every Cloud Run service whose name starts with nimbus")
    ap.add_argument("--token", default=os.environ.get("NIMBUS_ADMIN_TOKEN", ""))
    ap.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT", "adsc-nimbus"))
    ap.add_argument("--region", default=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"))
    args = ap.parse_args()

    if args.all_services:
        listing = subprocess.run(
            ["gcloud", "run", "services", "list", f"--project={args.project}",
             f"--region={args.region}", "--format=value(metadata.name,status.url)"],
            capture_output=True, text=True)
        targets = [tuple(line.split("\t")) for line in listing.stdout.splitlines()
                   if line.startswith("nimbus")]
        if not targets:
            sys.exit("no nimbus services are deployed.")
    elif args.url:
        targets = [(args.url.rstrip("/").split("//")[-1].split(".")[0], args.url)]
    else:
        ap.error("give --url or --all-services")

    failed = {}
    for name, url in targets:
        print(f"\n  {name}  {url}")
        problems = check(url.rstrip("/"), args.token)
        if problems:
            failed[name] = problems
            for p in problems:
                print(f"    FAIL      {p}")

    print()
    if failed:
        print(f"NOT READY -- {len(failed)} of {len(targets)} service(s) have problems:")
        for name, problems in failed.items():
            for p in problems:
                print(f"  {name}: {p}")
        sys.exit(1)
    print(f"All {len(targets)} service(s) ready to hand out.")


if __name__ == "__main__":
    main()
