"""Nouba service facade over the unified Meta adapter."""
from .integrations.whatsapp import WhatsAppClient, verify_signature
from .integrations.errors import IntegrationError
from .ai import AIError

async def _call(method, *args):
    try:
        return await getattr(WhatsAppClient(), method)(*args)
    except IntegrationError as exc:
        raise AIError(exc.code) from None

async def send_text(phone, text):
    return await _call("send_text", phone, text)

async def send_interactive(phone, payload):
    return await _call("send_interactive", phone, payload)

async def download_media(media_id):
    return await _call("download_media", media_id)

async def send_template(phone, name, language, parameters):
    return await _call("send_template", phone, name, language, parameters)
