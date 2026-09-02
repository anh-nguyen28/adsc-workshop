"""Contract tests for the Google model adapter.

These tests use httpx's in-process transport, so they do not need Google
credentials, a cloud project, or a live model request. They protect the wire
format and the failure behavior that the participant service depends on.
"""
import json
import os
import pathlib
import sys
import unittest
from unittest.mock import AsyncMock, patch

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "01_deploy"))

import cloud_model  # noqa: E402


class CloudModelContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.old_http = cloud_model._http
        self.old_project = cloud_model._project
        self.old_access_token = cloud_model._access_token
        cloud_model._project = "test-project"
        cloud_model._access_token = AsyncMock(return_value="test-token")

    async def asyncTearDown(self):
        if cloud_model._http is not None and cloud_model._http is not self.old_http:
            await cloud_model._http.aclose()
        cloud_model._http = self.old_http
        cloud_model._project = self.old_project
        cloud_model._access_token = self.old_access_token

    async def _generate(self, handler, **env):
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        cloud_model._http = client
        stats = {}
        with patch.dict(os.environ, {
            "NIMBUS_GOOGLE_API_STYLE": "mistral",
            "NIMBUS_GOOGLE_MODEL_ID": "mistral-small-2503",
            "NIMBUS_PROVIDER_RETRIES": "0",
            "NIMBUS_PROVIDER_BACKOFF_SECONDS": "0",
            **env,
        }, clear=False):
            chunks = [chunk async for chunk in cloud_model.generate(
                "large", "test prompt", 8, stats)]
        return chunks, stats

    async def test_parses_sse_text_and_usage(self):
        def handler(request):
            payload = json.loads(request.content)
            self.assertEqual(payload["model"], "mistral-small-2503")
            self.assertEqual(payload["temperature"], 0)
            body = (
                'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
                'data: {"choices":[{"delta":{"content":" world"}}],'
                '"usage":{"prompt_tokens":11,"completion_tokens":2}}\n\n'
                "data: [DONE]\n\n"
            )
            return httpx.Response(200, headers={"content-type": "text/event-stream"},
                                  content=body)

        chunks, stats = await self._generate(handler)
        self.assertEqual(chunks, ["hello", " world"])
        self.assertEqual(stats["tokens_in"], 11)
        self.assertEqual(stats["tokens_out"], 2)
        self.assertEqual(stats["usage_source"], "provider")

    async def test_parses_complete_json_response(self):
        def handler(request):
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"choices": [{"message": {"content": "complete"}}],
                      "usage": {"input_tokens": 7, "output_tokens": 1}},
            )

        chunks, stats = await self._generate(handler)
        self.assertEqual(chunks, ["complete"])
        self.assertEqual(stats["tokens_in"], 7)
        self.assertEqual(stats["tokens_out"], 1)

    async def test_retries_transient_provider_failure(self):
        attempts = 0

        def handler(request):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return httpx.Response(429, text="busy")
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"choices": [{"message": {"content": "retry ok"}}]},
            )

        chunks, _ = await self._generate(
            handler, NIMBUS_PROVIDER_RETRIES="1")
        self.assertEqual(attempts, 2)
        self.assertEqual(chunks, ["retry ok"])


if __name__ == "__main__":
    unittest.main()
