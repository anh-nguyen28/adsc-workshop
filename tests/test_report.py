"""Regression tests for local-provider cost reporting."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "02_benchmark"))

import report  # noqa: E402


class ReportTests(unittest.TestCase):
    def test_ollama_is_reported_as_zero_direct_cost(self):
        payload = {
            "run": 1,
            "duration_s": 1.0,
            "server_runtime": {"provider": "ollama"},
            "server_config": {},
            "results": [{
                "ok": True,
                "shed": False,
                "latency_s": 1.0,
                "ttft_s": 0.2,
                "queue_wait_ms": 0.0,
                "compute_ms": 1000.0,
                "tokens_in": 100,
                "tokens_out": 20,
                "tokens_cached": 0,
                "usage_source": "provider",
                "provider": "ollama",
                "model": "llama3.1:8b",
                "cache": "miss",
                "tier": "large",
            }],
        }
        scenario = {
            "prices": {"large": {"input": 0.6, "output": 2.4},
                        "replica_usd_per_month": 300},
            "traffic": {"requests_per_day": 1},
            "constraints": {"slo_p95_latency_s": 5.0, "budget_usd_per_month": 1500},
        }

        summary = report.summarise(payload, scenario)

        self.assertEqual(summary["provider"], "ollama")
        self.assertTrue(summary["usage_complete"])
        self.assertEqual(summary["usd_per_month"], 0.0)
        self.assertEqual(summary["usd_infra_per_month"], 0.0)


if __name__ == "__main__":
    unittest.main()
