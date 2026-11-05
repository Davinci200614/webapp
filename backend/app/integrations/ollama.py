from typing import Any

import httpx

from .. import config
from ..diagnostics import event
from .errors import IntegrationError


class OllamaClient:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        base_url: str | None = None,
    ):
        self._client = client
        self._base_url = (base_url or config.OLLAMA_BASE_URL).rstrip("/")

    async def generate_json(
        self, prompt: str, *, model: str | None = None
    ) -> dict[str, Any]:
        selected_model = model or config.OLLAMA_MODEL
        if not selected_model:
            raise IntegrationError("ollama_model_not_configured")
        payload = {
            "model": selected_model,
            "stream": False,
            "think": False,
            "format": "json",
            "options": {
                "num_ctx": config.OLLAMA_NUM_CTX,
                "num_predict": config.OLLAMA_NUM_PREDICT,
                "temperature": 0,
            },
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            if self._client is not None:
                response = await self._client.post(
                    f"{self._base_url}/api/chat", json=payload
                )
            else:
                async with httpx.AsyncClient(
                    timeout=config.OLLAMA_TIMEOUT_SECONDS, trust_env=False
                ) as client:
                    response = await client.post(
                        f"{self._base_url}/api/chat", json=payload
                    )
            if response.status_code == 404:
                raise IntegrationError("ollama_model_unavailable")
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content")
            if not isinstance(content, str) or not content.strip():
                raise IntegrationError("ollama_invalid_json")
            import json

            result = json.loads(content)
            if not isinstance(result, dict):
                raise IntegrationError("ollama_invalid_json")
            event("ollama.generate_json", outcome="ok", model=selected_model)
            return result
        except IntegrationError:
            raise
        except httpx.TimeoutException:
            raise IntegrationError("ollama_timeout") from None
        except httpx.ConnectError:
            raise IntegrationError("ollama_offline") from None
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            raise IntegrationError("ollama_transport_error") from None
