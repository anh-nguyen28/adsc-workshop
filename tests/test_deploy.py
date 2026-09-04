"""A deployed incident must be complete the moment the container starts.

An incident's configuration lives in two halves -- lever-settable and
deploy-only -- and calibration hides the difference by applying the lever half
over HTTP after the service is up. A real team's service has no such step.

Every failure guarded here was real, and every one of them is silent: the
service starts healthy, answers requests, and is simply not the incident it was
supposed to be.
"""
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "facilitators"))

import deploy_incident  # noqa: E402
from incidents import HEALTHY_ENV, INCIDENTS  # noqa: E402

DEPLOY_SH = (ROOT / "deploy" / "deploy.sh").read_text()
FORWARDED = set(re.findall(r"[@^](NIMBUS_[A-Z_]+)=", DEPLOY_SH))


class DeployForwardsEverythingTests(unittest.TestCase):
    def test_every_lever_an_incident_needs_reaches_the_container(self):
        """deploy.sh silently dropped three of them.

        MODEL_TIER is the whole of cheapmodel's fault and SEMANTIC_CACHE_THRESHOLD
        is the whole of staleness's. Deployed without them, both services ran the
        healthy configuration and the incident was simply absent -- no error, no
        warning, just a team diagnosing a service with nothing wrong.
        """
        needed = set(HEALTHY_ENV)
        for spec in INCIDENTS.values():
            needed |= set(spec["env"])
        missing = sorted(needed - FORWARDED)
        self.assertEqual(missing, [], f"deploy.sh does not forward: {missing}")

    def test_the_fault_of_each_incident_survives_deployment(self):
        for name, key in (("cheapmodel", "NIMBUS_MODEL_TIER"),
                          ("staleness", "NIMBUS_SEMANTIC_CACHE_THRESHOLD"),
                          ("decode", "NIMBUS_MAX_TOKENS"),
                          ("queue", "NIMBUS_MAX_CONCURRENT"),
                          ("prompt", "NIMBUS_RETRIEVE_K"),
                          ("retrieval", "NIMBUS_INCIDENT_STAGE_DELAY"),
                          ("upstream", "NIMBUS_INCIDENT_PROVIDER_FAULT")):
            with self.subTest(incident=name):
                env = deploy_incident.env_for(name, "svc", True)
                self.assertIn(key, env)
                self.assertIn(key, FORWARDED)


class DeployEnvIsCompleteTests(unittest.TestCase):
    def test_healthy_levers_are_pinned_even_when_the_incident_omits_them(self):
        """An incident that does not mention a lever must still pin it.

        Otherwise it inherits whatever the deployment defaults happen to be, and
        two incidents differ by more than the one thing they are supposed to.
        """
        env = deploy_incident.env_for("upstream", "svc", True)
        for key in HEALTHY_ENV:
            self.assertIn(key, env)

    def test_the_incident_overrides_the_healthy_value(self):
        self.assertEqual(HEALTHY_ENV["NIMBUS_MODEL_TIER"], "large")
        env = deploy_incident.env_for("cheapmodel", "svc", True)
        self.assertEqual(env["NIMBUS_MODEL_TIER"], "small")

    def test_decode_is_born_with_a_workable_output_cap(self):
        """Pro plus thinking at MAX_TOKENS=32 answered every question 'Hello'.

        The incident is meant to be slow and expensive, not mute.
        """
        env = deploy_incident.env_for("decode", "svc", True)
        self.assertEqual(env["NIMBUS_MAX_TOKENS"], "256")
        self.assertEqual(env["NIMBUS_GOOGLE_MODEL_LARGE"], "gemini-2.5-pro")
        self.assertEqual(env["NIMBUS_GEMINI_THINKING_BUDGET"], "128")

    def test_a_team_service_never_scales_to_zero(self):
        """A cold container moved the dominant ledger row onto the wrong
        component, so the first benchmark of the session would diagnose the
        platform instead of the incident."""
        env = deploy_incident.env_for("queue", "svc", True)
        self.assertEqual(env["NIMBUS_MIN_INSTANCES"], "1")

    def test_the_gate_can_be_left_off_for_round_one(self):
        self.assertEqual(
            deploy_incident.env_for("queue", "svc", False)["NIMBUS_REQUIRE_HYPOTHESIS"],
            "false")

    def test_unknown_incidents_are_refused(self):
        with self.assertRaises(KeyError):
            deploy_incident.env_for("not-an-incident", "svc", True)


if __name__ == "__main__":
    unittest.main()


class RoundSwitchTests(unittest.TestCase):
    """Round 1 is shared; round 2 is not. Neither can wait on a redeploy.

    Queue is entirely lever-settable, but three round-2 incidents carry
    deploy-time injection that fires from container start -- so one service
    cannot serve both rounds cleanly, and a redeploy costs minutes a 20-minute
    activity does not have. Two services per team, and the switch is a URL.
    """

    def _plan(self, teams, rounds=True):
        import argparse
        names = sorted(n for n, s in INCIDENTS.items() if s.get("round") == 2)
        assigned = [names[i % len(names)] for i in range(teams)]
        out = []
        for i, incident in enumerate(assigned):
            team = f"nimbus-team-{chr(ord('a') + i)}"
            if rounds:
                out.append(("queue", f"{team}-r1"))
            out.append((incident, f"{team}-r2" if rounds else team))
        return out

    def test_each_team_gets_a_round_one_and_a_round_two_service(self):
        plan = self._plan(6)
        self.assertEqual(len(plan), 12)
        self.assertEqual(sum(1 for i, _ in plan if i == "queue"), 6)

    def test_round_one_is_the_same_incident_for_everyone(self):
        r1 = [i for i, s in self._plan(6) if s.endswith("-r1")]
        self.assertEqual(set(r1), {"queue"})

    def test_neighbouring_teams_get_different_round_two_incidents(self):
        r2 = [i for i, s in self._plan(4) if s.endswith("-r2")]
        self.assertEqual(len(set(r2)), 4, "four teams must get four faults")

    def test_more_teams_than_incidents_duplicates_rather_than_failing(self):
        r2 = [i for i, s in self._plan(6) if s.endswith("-r2")]
        self.assertEqual(len(r2), 6)
        # Neighbours still differ, which is what the poll beat depends on.
        for a, b in zip(r2, r2[1:]):
            self.assertNotEqual(a, b)

    def test_the_gate_is_off_in_round_one_and_on_in_round_two(self):
        for incident, service in self._plan(2):
            gate = not service.endswith("-r1")
            env = deploy_incident.env_for(incident, service, gate)
            expected = "false" if service.endswith("-r1") else "true"
            self.assertEqual(env["NIMBUS_REQUIRE_HYPOTHESIS"], expected, service)

    def test_a_round_one_service_carries_no_injection(self):
        """Round 1 must be the capacity incident and nothing else.

        Checks the injection keys specifically. "any key containing INCIDENT"
        was the old proxy, and it stopped meaning what it said once the PUBLIC
        half of the brief started travelling as NIMBUS_INCIDENT_TITLE and
        friends -- those are the symptom, which participants are meant to have.
        """
        env = deploy_incident.env_for("queue", "nimbus-team-a-r1", False)
        injection = ("NIMBUS_INCIDENT_STAGE_DELAY", "NIMBUS_INCIDENT_PROVIDER_FAULT")
        self.assertFalse([k for k in injection if k in env])
        self.assertEqual(env["NIMBUS_MAX_CONCURRENT"], "1")


class PublicBriefTests(unittest.TestCase):
    """The symptom ships with the service. The cause never does."""

    def test_every_incident_ships_its_public_symptom(self):
        for name in INCIDENTS:
            env = deploy_incident.env_for(name, "svc", True)
            self.assertTrue(env["NIMBUS_INCIDENT_BRIEF"].strip(), name)
            self.assertTrue(env["NIMBUS_INCIDENT_TITLE"].strip(), name)

    def test_the_private_truth_never_reaches_the_deployment(self):
        """The whole design rests on this: participants get the symptom and the
        instruments, never the answer."""
        for name, spec in INCIDENTS.items():
            env = deploy_incident.env_for(name, "svc", True)
            shipped = " ".join(env.values()).lower()
            for secret in ("private_truth", "discriminator",
                           "tempting_wrong_fix", "correct_path"):
                self.assertNotIn(spec[secret].lower(), shipped,
                                 f"{name} leaks its {secret}")

    def test_the_brief_does_not_name_a_lever(self):
        levers = ("RESPONSE_CACHE", "SEMANTIC_CACHE", "MAX_TOKENS", "MODEL_TIER",
                  "MAX_CONCURRENT", "RETRIEVE_K", "SYSTEM_PROMPT", "ROUTE_EASY")
        for name, spec in INCIDENTS.items():
            text = (spec["public_symptom"] + " " + spec["user_impact"]).upper()
            for lever in levers:
                self.assertNotIn(lever, text, f"{name}'s brief names {lever}")


class UpstreamFaultRateTests(unittest.TestCase):
    def test_the_fault_rate_produces_a_visible_tell_on_the_real_corpus(self):
        """The fault is seeded from the prompt, so it is fixed per corpus.

        Choosing the rate from the binomial is the wrong instrument: at 0.17 and
        0.20 exactly one of the first sixteen benchmark requests faulted, every
        run. At 0.25 five fault and one fails outright, so the run reports
        "15 ok / 1 failed" beside the retry count.
        """
        rate = INCIDENTS["upstream"]["env"]["NIMBUS_INCIDENT_PROVIDER_FAULT"]
        self.assertEqual(rate.split(":")[0], "0.25")
        self.assertGreaterEqual(INCIDENTS["upstream"]["expect"]["at_least"], 3)

    def test_the_public_title_does_not_name_the_fault(self):
        """`title` is the facilitator's name and several give the answer away.

        "The new vector store" told a participant exactly where to look, before
        they had measured anything.
        """
        giveaways = ("vector store", "cheap-model", "provider", "thinking",
                     "cache", "prompt", "concurrency", "queue", "model")
        for name, spec in INCIDENTS.items():
            title = spec["public_title"].lower()
            for word in giveaways:
                self.assertNotIn(word, title,
                                 f"{name}'s public title says {word!r}")

    def test_the_deployment_ships_the_public_title_not_the_internal_one(self):
        for name, spec in INCIDENTS.items():
            env = deploy_incident.env_for(name, "svc", True)
            self.assertEqual(env["NIMBUS_INCIDENT_TITLE"], spec["public_title"])
            if spec["public_title"] != spec["title"]:
                self.assertNotEqual(env["NIMBUS_INCIDENT_TITLE"], spec["title"])
