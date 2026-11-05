import asyncio
import json
import time
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.responses import PlainTextResponse

from . import config
from .db import init_db
from . import inbox
from .service import handle_message
from contextlib import suppress
from .auth import provision_bootstrap
from .diagnostics import event, configure_logging
from .integrations.whatsapp import verify_signature
from .routes.machines import router as machines_router
from .routes.requests import router as requests_router
from .routes.auth import router as auth_router


@asynccontextmanager
async def lifespan(app):
    configure_logging()
    init_db()
    provision_bootstrap()
    with inbox.connect() as db:
        db.execute("UPDATE webhook_inbox SET state='pending' WHERE state='running'")
    event('application.ready', outcome='ok', state='webhook_ready')
    worker = asyncio.create_task(inbox.run())
    try:
        yield
    finally:
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker


app = FastAPI(title=config.APP_NAME, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)
app.include_router(requests_router)
app.include_router(machines_router)
app.include_router(auth_router)
from .routes.employment import router as employment_router
from .routes.inspection import router as inspection_router
app.include_router(employment_router)
app.include_router(inspection_router)

@app.get('/api/public/config')
def public_config():
    return {'whatsapp_number': config.WHATSAPP_CONTACT_NUMBER}



@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/webhook/whatsapp")
def verify_webhook(request: Request) -> str:
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and config.META_VERIFY_TOKEN
        and params.get("hub.verify_token") == config.META_VERIFY_TOKEN
    ):
        return PlainTextResponse(params.get("hub.challenge", ""))
    raise HTTPException(status_code=403, detail="Invalid verification token")


async def process_messages(messages):
    await asyncio.gather(*(handle_message(message) for message in messages))


async def _process_messages(messages):
    inbox.enqueue(messages)
    await inbox.drain()


@app.post("/webhook/whatsapp")
async def receive_webhook(request: Request, tasks: BackgroundTasks) -> dict[str, bool]:
    event('webhook.received', outcome='received')
    if not config.CONVERSATION_ENABLED:
        raise HTTPException(status_code=503, detail="Conversation controller disabled")
    started = time.monotonic()
    body = await request.body()
    if not verify_signature(body, request.headers.get("x-hub-signature-256")):
        event("webhook.signature", outcome="rejected")
        raise HTTPException(status_code=403, detail="Invalid webhook signature")
    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON") from None
    if not isinstance(payload, dict):
        raise HTTPException(400, "Invalid webhook payload")
    try:
        messages = [
            message
            for entry in payload.get("entry", [])
            for change in entry.get("changes", [])
            for message in change.get("value", {}).get("messages", [])
        ]
    except (AttributeError, TypeError):
        raise HTTPException(400, 'Invalid webhook envelope') from None
    event("webhook.parsed", outcome="ok", message_count=len(messages))
    if messages:
        inbox.enqueue(messages)
        tasks.add_task(inbox.drain)
    return {"received": True}

# The built SPA can be served directly by FastAPI, including deep links.
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
_frontend = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
if (_frontend / 'assets').is_dir():
    app.mount('/assets', StaticFiles(directory=_frontend / 'assets'), name='assets')

@app.get('/', include_in_schema=False)
@app.get('/{page}', include_in_schema=False)
def frontend_page(page: str = ''):
    if page not in {'', 'catalogue', 'catalogue.html', 'cooperative', 'cooperative.html',
                    'operations', 'equipe-machinati.html', 'requests', 'machines',
                    'employment', 'inspect', 'privacy', 'terms', 'data-deletion'}:
        raise HTTPException(404, 'Page not found')
    if not (_frontend / 'index.html').is_file():
        raise HTTPException(404, 'Build the frontend with npm run build first')
    return FileResponse(_frontend / 'index.html')
