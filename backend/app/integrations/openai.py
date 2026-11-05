"""OpenAI Responses and transcription transport with safe diagnostic errors."""
import asyncio
from copy import deepcopy
import json
from typing import Any

import httpx

from .. import config
from ..diagnostics import event
from .errors import IntegrationError


def strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Require every property for Structured Outputs; validate bounds locally.

    Pydantic represents optional facts as nullable fields. OpenAI requires these
    fields to be present even when their value is null, including nested objects.
    """
    def visit(value):
        if isinstance(value, list):
            return [visit(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {key: visit(item) for key, item in value.items()
                  if key not in {'default', 'title', 'format', 'minLength', 'maxLength',
                                 'minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum'}}
        if result.get('type') == 'object':
            result['additionalProperties'] = False
            result['required'] = list(result.get('properties', {}))
        return result
    return visit(deepcopy(schema))


class OpenAIClient:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def _post(self, path: str, **kwargs) -> dict[str, Any]:
        if not config.OPENAI_API_KEY:
            raise IntegrationError('openai_not_configured')
        kwargs['headers'] = {'Authorization': f'Bearer {config.OPENAI_API_KEY}'}
        url = f'https://api.openai.com/v1/{path}'
        try:
            async with asyncio.timeout(config.OPENAI_TIMEOUT_SECONDS):
                if self._client is not None:
                    response = await self._client.post(url, **kwargs)
                else:
                    async with httpx.AsyncClient(timeout=config.OPENAI_TIMEOUT_SECONDS, trust_env=False) as client:
                        response = await client.post(url, **kwargs)
            if response.status_code == 429:
                raise IntegrationError('openai_rate_limited')
            if response.status_code in (401, 403):
                raise IntegrationError('openai_auth_error')
            if response.status_code == 404:
                raise IntegrationError('openai_model_unavailable')
            if response.status_code == 400:
                raise IntegrationError('openai_invalid_request')
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise IntegrationError('openai_invalid_response')
            return result
        except IntegrationError:
            raise
        except (TimeoutError, httpx.TimeoutException):
            raise IntegrationError('openai_timeout') from None
        except (httpx.HTTPError, ValueError, TypeError):
            raise IntegrationError('openai_unavailable') from None

    async def generate_json(self, prompt: str, *, instructions: str, schema: dict[str, Any],
                            model: str | None = None) -> dict[str, Any]:
        model = model or config.OPENAI_MODEL
        if not model:
            raise IntegrationError('openai_model_not_configured')
        data = await self._post('responses', json={
            'model': model,
            'instructions': instructions,
            'input': prompt,
            'store': False,
            'max_output_tokens': 1600,
            'text': {'format': {'type': 'json_schema', 'name': 'agricultural_understanding',
                                'strict': True, 'schema': strict_schema(schema)}},
        })
        if data.get('status') != 'completed':
            raise IntegrationError('openai_incomplete_response')
        try:
            parts = [part for item in data.get('output', []) if item.get('type') == 'message'
                     for part in item.get('content', [])]
            if any(part.get('type') == 'refusal' for part in parts):
                raise IntegrationError('openai_refusal')
            raw = ''.join(part['text'] for part in parts if part.get('type') == 'output_text')
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError()
        except IntegrationError:
            raise
        except (ValueError, KeyError, TypeError, AttributeError):
            raise IntegrationError('openai_invalid_json') from None
        event('openai.generate_json', provider='openai', model=model, outcome='ok')
        return result

    async def transcribe(self, audio: bytes, mime_type: str = 'audio/ogg') -> str:
        if not audio or len(audio) > 14 * 1024 * 1024:
            raise IntegrationError('audio_empty_or_too_large')
        if not config.OPENAI_STT_MODEL:
            raise IntegrationError('openai_stt_model_not_configured')
        extension = {'audio/ogg': 'ogg', 'audio/opus': 'ogg', 'audio/mpeg': 'mp3',
                     'audio/mp3': 'mp3', 'audio/mp4': 'mp4', 'audio/m4a': 'm4a',
                     'audio/wav': 'wav', 'audio/flac': 'flac', 'audio/webm': 'webm'}.get(mime_type)
        if not extension:
            raise IntegrationError('audio_unsupported_format')
        data = await self._post('audio/transcriptions',
            files={'file': (f'voice.{extension}', audio, mime_type)},
            data={'model': config.OPENAI_STT_MODEL, 'response_format': 'json',
                  'prompt': 'Moroccan Darija, Arabic and French speech. Transcribe verbatim in the original language and script. Do not translate, answer, or invent missing words.'})
        text = data.get('text')
        if not isinstance(text, str) or not text.strip() or '[غير واضح]' in text:
            raise IntegrationError('transcription_unclear')
        event('openai.transcribe', provider='openai', model=config.OPENAI_STT_MODEL, outcome='ok')
        return text.strip()
