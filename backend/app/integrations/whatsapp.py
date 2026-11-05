import hashlib
import hmac
from typing import Any

import httpx

from .. import config
from ..diagnostics import event
from .errors import IntegrationError


GRAPH = "https://graph.facebook.com"


def verify_signature(body: bytes, header: str | None) -> bool:
    if not config.META_APP_SECRET or not header or not header.startswith("sha256="):
        return False
    digest = hmac.new(
        config.META_APP_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(header[7:], digest)


class WhatsAppClient:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        graph_url: str = GRAPH,
    ):
        self._client = client
        self._graph_url = graph_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        if not config.META_ACCESS_TOKEN:
            raise IntegrationError("whatsapp_not_configured")
        return {"Authorization": f"Bearer {config.META_ACCESS_TOKEN}"}

    async def _request(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        if self._client is not None:
            return await self._client.request(method, url, **kwargs)
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            return await client.request(method, url, **kwargs)

    async def download_media(self, media_id: str) -> bytes:
        if not media_id:
            raise IntegrationError("whatsapp_media_id_missing")
        headers = self._headers()
        try:
            metadata = await self._request(
                "GET",
                f"{self._graph_url}/{config.META_GRAPH_VERSION}/{media_id}",
                headers=headers,
            )
            metadata.raise_for_status()
            media_url = metadata.json().get("url")
            if not isinstance(media_url, str) or not media_url:
                raise IntegrationError("whatsapp_media_url_missing")
            response = await self._request("GET", media_url, headers=headers)
            response.raise_for_status()
            return response.content
        except IntegrationError:
            raise
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            raise IntegrationError("whatsapp_media_unavailable") from None

    async def send_text(self, to: str, text: str) -> dict[str, Any]:
        return await self._send(to, {"type": "text", "text": {"body": text}})

    async def send_template(self, to: str, name: str, language: str, parameters: list[str]):
        return await self._send(to, {'type':'template','template':{'name':name,'language':{'code':language},
            'components':[{'type':'body','parameters':[{'type':'text','text':value} for value in parameters]}]}})

    async def send_interactive(
        self, to: str, interactive: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._send(to, {"type": "interactive", "interactive": interactive})

    async def _send(self, to: str, content: dict[str, Any]) -> dict[str, Any]:
        if not to:
            raise IntegrationError("whatsapp_recipient_missing")
        if not config.META_PHONE_NUMBER_ID:
            raise IntegrationError("whatsapp_not_configured")
        headers = self._headers()
        payload = {"messaging_product": "whatsapp", "to": to, **content}
        try:
            response = await self._request(
                "POST",
                f"{self._graph_url}/{config.META_GRAPH_VERSION}/"
                f"{config.META_PHONE_NUMBER_ID}/messages",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise IntegrationError("whatsapp_invalid_response")
            event("whatsapp.send", outcome="accepted", status=response.status_code)
            return result
        except IntegrationError:
            raise
        except (httpx.HTTPError, ValueError, TypeError):
            raise IntegrationError("whatsapp_send_failed") from None
