import hashlib
import hmac
import json
import unittest
from unittest.mock import patch

import httpx

from app.integrations.errors import IntegrationError
from app.integrations.gemini import GeminiClient
from app.integrations.ollama import OllamaClient
from app.integrations.whatsapp import WhatsAppClient, verify_signature


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    def test_whatsapp_signature_accepts_only_matching_hmac(self):
        body = b'{"entry":[]}'
        secret = "test-secret"
        digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        with patch("app.integrations.whatsapp.config.META_APP_SECRET", secret):
            self.assertTrue(verify_signature(body, f"sha256={digest}"))
            self.assertFalse(verify_signature(body, "sha256=invalid"))
            self.assertFalse(verify_signature(body, None))

    async def test_whatsapp_media_download_and_send_are_redacted_adapters(self):
        requests = []

        async def handler(request):
            requests.append(request)
            if request.method == "GET" and request.url.path.endswith("/media-id"):
                return httpx.Response(200, json={"url": "https://media.test/audio"})
            if request.method == "GET":
                return httpx.Response(200, content=b"audio")
            return httpx.Response(200, json={"messages": [{"id": "out-1"}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch("app.integrations.whatsapp.config.META_ACCESS_TOKEN", "secret"), patch(
                "app.integrations.whatsapp.config.META_PHONE_NUMBER_ID", "phone"
            ):
                adapter = WhatsAppClient(client, graph_url="https://graph.test")
                self.assertEqual(await adapter.download_media("media-id"), b"audio")
                result = await adapter.send_text("212600000000", "hello")

        self.assertEqual(result["messages"][0]["id"], "out-1")
        self.assertEqual(requests[-1].headers["authorization"], "Bearer secret")

    async def test_whatsapp_missing_credentials_is_safe(self):
        with patch("app.integrations.whatsapp.config.META_ACCESS_TOKEN", ""):
            with self.assertRaisesRegex(IntegrationError, "whatsapp_not_configured"):
                await WhatsAppClient().send_text("recipient", "hello")

    async def test_gemini_success_and_invalid_json(self):
        async def handler(request):
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {"content": {"parts": [{"text": json.dumps({"intent": "machine"})}]}}
                    ]
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch("app.integrations.gemini.config.GEMINI_API_KEY", "key"), patch(
                "app.integrations.gemini.config.GEMINI_MODEL", "model"
            ):
                result = await GeminiClient(client, endpoint="https://gemini.test").generate_json(
                    "classify"
                )
        self.assertEqual(result, {"intent": "machine"})

        async def invalid_handler(request):
            return httpx.Response(
                200,
                json={"candidates": [{"content": {"parts": [{"text": "not-json"}]}}]},
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(invalid_handler)
        ) as client:
            with patch("app.integrations.gemini.config.GEMINI_API_KEY", "key"), patch(
                "app.integrations.gemini.config.GEMINI_MODEL", "model"
            ):
                with self.assertRaisesRegex(IntegrationError, "gemini_invalid_json"):
                    await GeminiClient(client, endpoint="https://gemini.test").generate_json(
                        "classify"
                    )

    async def test_gemini_timeout_rate_limit_and_missing_key(self):
        async def timeout_handler(request):
            raise httpx.ReadTimeout("timed out")

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(timeout_handler)
        ) as client:
            with patch("app.integrations.gemini.config.GEMINI_API_KEY", "key"), patch(
                "app.integrations.gemini.config.GEMINI_MODEL", "model"
            ):
                with self.assertRaisesRegex(IntegrationError, "gemini_timeout"):
                    await GeminiClient(client, endpoint="https://gemini.test").generate_json(
                        "classify"
                    )

        async def rate_limit_handler(request):
            return httpx.Response(429)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(rate_limit_handler)
        ) as client:
            with patch("app.integrations.gemini.config.GEMINI_API_KEY", "key"), patch(
                "app.integrations.gemini.config.GEMINI_MODEL", "model"
            ):
                with self.assertRaisesRegex(IntegrationError, "gemini_rate_limited"):
                    await GeminiClient(client, endpoint="https://gemini.test").generate_json(
                        "classify"
                    )

        with patch("app.integrations.gemini.config.GEMINI_API_KEY", ""):
            with self.assertRaisesRegex(IntegrationError, "gemini_not_configured"):
                await GeminiClient().generate_json("classify")

    async def test_ollama_success_offline_timeout_and_missing_model(self):
        async def success_handler(request):
            return httpx.Response(
                200,
                json={"message": {"content": json.dumps({"task": "machine"})}},
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(success_handler)
        ) as client:
            with patch("app.integrations.ollama.config.OLLAMA_MODEL", "qwen"):
                result = await OllamaClient(client, base_url="http://ollama.test").generate_json(
                    "classify"
                )
        self.assertEqual(result, {"task": "machine"})

        async def offline_handler(request):
            raise httpx.ConnectError("offline")

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(offline_handler)
        ) as client:
            with patch("app.integrations.ollama.config.OLLAMA_MODEL", "qwen"):
                with self.assertRaisesRegex(IntegrationError, "ollama_offline"):
                    await OllamaClient(client, base_url="http://ollama.test").generate_json(
                        "classify"
                    )

        async def timeout_handler(request):
            raise httpx.ReadTimeout("timed out")

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(timeout_handler)
        ) as client:
            with patch("app.integrations.ollama.config.OLLAMA_MODEL", "qwen"):
                with self.assertRaisesRegex(IntegrationError, "ollama_timeout"):
                    await OllamaClient(client, base_url="http://ollama.test").generate_json(
                        "classify"
                    )

        async def missing_handler(request):
            return httpx.Response(404)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(missing_handler)
        ) as client:
            with patch("app.integrations.ollama.config.OLLAMA_MODEL", "qwen"):
                with self.assertRaisesRegex(IntegrationError, "ollama_model_unavailable"):
                    await OllamaClient(client, base_url="http://ollama.test").generate_json(
                        "classify"
                    )

        with patch("app.integrations.ollama.config.OLLAMA_MODEL", ""):
            with self.assertRaisesRegex(IntegrationError, "ollama_model_not_configured"):
                await OllamaClient().generate_json("classify")
