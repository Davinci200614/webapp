import asyncio
import json
from typing import Any

import httpx

from .. import config
from ..diagnostics import event
from .errors import IntegrationError


class GeminiClient:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        endpoint: str = "https://generativelanguage.googleapis.com/v1beta",
    ):
        self._client = client
        self._endpoint = endpoint.rstrip("/")

    async def _request(self, model: str, contents: list[dict[str, Any]], generation_config: dict[str, Any] | None = None) -> dict[str, Any]:
        if not config.GEMINI_API_KEY:
            raise IntegrationError("gemini_not_configured")
        if not model:
            raise IntegrationError("gemini_model_not_configured")
        payload: dict[str, Any] = {"contents": contents}
        if generation_config:
            payload["generationConfig"] = generation_config
        try:
            if self._client is not None:
                response = await self._client.post(
                    f"{self._endpoint}/models/{model}:generateContent",
                    headers={"x-goog-api-key": config.GEMINI_API_KEY},
                    json=payload,
                )
            else:
                async with httpx.AsyncClient(
                    timeout=60, trust_env=False
                ) as client:
                    response = await client.post(
                        f"{self._endpoint}/models/{model}:generateContent",
                        headers={"x-goog-api-key": config.GEMINI_API_KEY},
                        json=payload,
                    )
            if response.status_code == 429:
                raise IntegrationError("gemini_rate_limited")
            if response.status_code in {401, 403}:
                raise IntegrationError("gemini_auth_error")
            if response.status_code in {400, 404}:
                raise IntegrationError("gemini_model_or_input_unavailable")
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise IntegrationError("gemini_invalid_response")
            return data
        except IntegrationError:
            raise
        except asyncio.TimeoutError:
            raise IntegrationError("gemini_timeout") from None
        except httpx.TimeoutException:
            raise IntegrationError("gemini_timeout") from None
        except httpx.NetworkError:
            raise IntegrationError("gemini_network_error") from None
        except (httpx.HTTPError, ValueError, TypeError):
            raise IntegrationError("gemini_unavailable") from None

    @staticmethod
    def _text(data: dict[str, Any]) -> str:
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            raise IntegrationError("gemini_empty_response") from None
        if not isinstance(text, str) or not text.strip():
            raise IntegrationError("gemini_empty_response")
        return text.strip()

    async def generate_json(
        self,
        prompt: str,
        *,
        model: str | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        generation_config: dict[str, Any] = {
            "temperature": 0,
            "responseMimeType": "application/json",
        }
        if response_schema:
            generation_config["responseJsonSchema"] = response_schema
        data = await self._request(
            model or config.GEMINI_MODEL,
            [{"role": "user", "parts": [{"text": prompt}]}],
            generation_config,
        )
        try:
            result = json.loads(self._text(data))
        except json.JSONDecodeError:
            raise IntegrationError("gemini_invalid_json") from None
        if not isinstance(result, dict):
            raise IntegrationError("gemini_invalid_json")
        event("gemini.generate_json", outcome="ok")
        return result

    async def transcribe(
        self, audio: bytes, mime_type: str = "audio/ogg"
    ) -> str:
        if not audio:
            raise IntegrationError("audio_empty")
        encoded = __import__("base64").b64encode(audio).decode("ascii")
        data = await self._request(
            config.GEMINI_STT_MODEL or config.GEMINI_MODEL,
            [
                {
                    "role": "user",
                    "parts": [
                        {"inlineData": {"mimeType": mime_type, "data": encoded}},
                        {"text": "Transcribe only the speech in this audio."},
                    ],
                }
            ],
        )
        text = self._text(data)
        event("gemini.transcribe", outcome="ok")
        return text
