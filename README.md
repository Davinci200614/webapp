# MACHINATI × Nouba integrated application

`webapp` is self-contained: it does not import runtime modules or databases from either source
repository. It combines Nouba's intent-first conversation, guided WhatsApp choices, employment
publication/search and inspector with MACHINATI's catalogue, cooperative/operations views,
inventory management, machine-fit scoring, priority explanations and urgency verification.

## One-command startup

```bash
cd webapp
./start.sh
```

This creates the backend virtual environment and installs dependencies when missing, builds the
React frontend, and starts **one backend process serving both the webpages and WhatsApp bot**
at `http://localhost:8000`. It preserves an existing `.env` and never displays its secrets.
Missing bot credentials are reported as warnings so public pages can still start. Missing
bootstrap credentials only prevent first-time private-dashboard login; a public WhatsApp
contact number is only needed for website handoff links.

Stop with Ctrl+C. The launcher starts or reuses ngrok for port 8000 and prints the callback URL.
Use `--no-ngrok` for a separately managed tunnel. Meta configuration is not changed.
It refuses occupied ports by default. To stop and replace an existing **webapp** server
without manually finding PIDs, run:

```bash
./start.sh --restart --no-build
# Rebuild the webpages as well:
./start.sh --restart
# Restart both development servers:
./start.sh --dev --restart
```

Restart verification uses Linux `/proc`, the current user, exact project directory and server
command/port. It includes reload-worker descendants and resumes Ctrl+Z-suspended processes so
they can terminate. It waits up to 15 seconds for graceful shutdown, then force-stops verified survivors.
Unrelated services and either original repository are left alone. A requested frontend build
finishes before the running backend is stopped. `--check --restart` does not stop anything.

For frontend/backend hot reload, use `./start.sh --dev` and open `http://localhost:5173`.
Ctrl+C or failure of either service shuts down both process groups. Use `./start.sh --check`
for prerequisite/configuration diagnostics without starting or installing anything,
`./start.sh --install` to refresh pinned dependencies, or `./start.sh --no-build` to serve
an existing bundle without Node/npm. `WEBAPP_PYTHON=/path/to/python ./start.sh` selects an
already provisioned Python environment. Run `./start.sh --help` for options.

## Run manually

Backend (Python 3.12+):

```bash
cd webapp/backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock.txt
cp .env.example .env
```

For the ready-to-copy OpenAI configuration and a field-by-field guide, see [ENV_SETUP.md](ENV_SETUP.md).

Set `AUTH_BOOTSTRAP_EMAIL` and `AUTH_BOOTSTRAP_PASSWORD` (at least 12 characters) in `.env` to
provision the first administrator. Remove the bootstrap password from the environment after
provisioning. The example selects OpenAI: set `OPENAI_API_KEY`, with `OPENAI_MODEL=gpt-4.1-mini`
and `OPENAI_STT_MODEL=gpt-4o-mini-transcribe` as configurable defaults. Gemini and Ollama
remain optional alternatives. Provider credentials are not required for the health endpoint
or dashboard. Set `WHATSAPP_CONTACT_NUMBER` to the business's public number to
enable catalogue and directory WhatsApp links.

```bash
python -m uvicorn app.main:app --reload
```

Frontend, from a second terminal:

```bash
cd webapp/frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` and `/health` to port 8000.
For one-server operation, run `npm run build` in `frontend` **before starting the backend**;
FastAPI serves the compiled SPA, assets and supported deep links on port 8000.
Configure the deployment's HTTPS URL and explicit `CORS_ORIGINS` when hosting separately.

## Pages and access

| URL | Behavior | Access |
|---|---|---|
| `/` | Live catalogue, machine/location filters, request estimator, browser dictation, WhatsApp handoff | Public |
| `/employment` | Confirmed worker profiles and job offers; type/location/text filters; WhatsApp publication links | Public |
| `/cooperative` | Inventory summary and approved requests by desired date | Operator |
| `/operations` | Status distribution, seven-day trend, local filters, request detail and inventory | Operator |
| `/requests` | Priority queue, machine-fit matches, urgency verification, approve/reject/complete | Operator |
| `/machines` | Full inventory view; create/edit ownership, rates, availability, date windows and notes | Operator read; admin write |
| `/inspect` | Stored messages/transcripts/replies, drafts, listings, inventory, requests, catalog and failed inbox retries | Admin, and `INSPECTOR_ENABLED=true` |
| `/privacy`, `/terms`, `/data-deletion` | Existing legal information and manual data-request procedure | Public |

Old catalogue/cooperative/operations HTML paths and `?view=` links resolve to their React views.
The UI uses session storage for bearer tokens, restores the current role with `/api/auth/me`,
and clears private data on logout or unauthorized responses. Request reads and mutations are
protected on the backend. Public employment responses include only confirmed publication fields,
never the private owner-phone linkage. Operators may withdraw inappropriate public listings.

The original IoT/verification panels and cooperative registration were prototypes without
backend services. This integration does not invent sensor data or a cooperative verification
service. Cooperative introductions now prepare a WhatsApp message. Desired-date planning is
based on approved requests; approval does not automatically book a machine or take payment.
Legal pages retain explicit placeholders for the operator's identity, contact and retention
policy; complete those operational details before public launch.

## WhatsApp and AI

Configure the four Meta credentials plus the public HTTPS callback:

- `GET /webhook/whatsapp`: Meta challenge verification.
- `POST /webhook/whatsapp`: HMAC-verified inbound messages, durably enqueued before acknowledgment.

Run **one backend process/worker** for this SQLite release. Each worker tick processes the first
eligible message per phone concurrently across different phones. Later messages from a phone
wait until its preceding message succeeds. Failed work retries with backoff up to five attempts;
failed rows remain visible for manual admin retry through the inspector. Running rows return to
pending at process startup. Do not use multiple Uvicorn workers: per-phone locks, restart recovery
and inbox ownership are intentionally process-local.

The original Nouba controller handles natural Darija/Arabic/French/Arabizi, machinery drafts,
relative dates, contextual short answers, corrections, cancel/reset/resume, worker/job drafts,
public searches, and native button/list choices. A summary must be delivered before an explicit
confirmation can publish a listing or create a `pending_review` request. Hashes bind confirmation
to the current draft; cached replies prevent redoing successful domain mutations on delivery retry.
Incoming text and transcriptions, user/assistant turns, dialogue audit and interactive payloads
are inspectable. Delivery is at least once: a process crash after Meta accepts a reply but before
its local delivery commit can cause that reply to be resent.

`CONVERSATION_PROVIDER=openai` selects OpenAI explicitly. `auto` prefers a configured OpenAI
key, then Gemini, otherwise Ollama.
`LLM_FALLBACK_PROVIDER` selects an explicit alternative after understanding errors. Each attempt
is bounded by `CONVERSATION_TIMEOUT_SECONDS`; fallback may use another attempt of that duration.
Deterministic guided flows remain usable during provider failures. OpenAI or Gemini STT is independent of
text understanding and validates audio before transcription. OpenAI uses the Responses API
with strict structured output and `store=false`, and accepts original OGG uploads for STT. Urgency declarations are included
in the confirmation summary and later require human verification.

`CONVERSATION_ENABLED=false` rejects new webhook intake with 503. It does not reroute traffic;
change the Meta callback/deployment routing explicitly to restore the original service.
Already accepted inbox work continues processing. `MUTATIONS_ENABLED=false` disables operational
API writes, while previously accepted WhatsApp work remains eligible for processing.

## Schema, backup and account provisioning

Startup applies numbered migrations and installs the shared alias catalog. Schema v4 adds the
durable inbox to the existing dialogue/employment, inventory and operator/session tables. No
legacy database is opened automatically. Relative database paths resolve against `backend`.

```bash
python -m scripts.seed_demo                 # optional, explicitly fictional records only
python -m scripts.import_legacy /archive/source.db /target/webapp.db --dry-run
python -m scripts.restore_database /backups/webapp.db.backup /restore/clean.db
python -m scripts.create_operator operator@example.com --role operator
```

The operator command prompts for a password and refuses duplicate accounts. Restore refuses to
overwrite an existing target. Import remains an explicit backup-first operation; keep the source
repositories/databases as independent rollback assets. Use SQLite's online backup API (available
as `app.db.backup_database`) when taking a backup while the app is running. Define retention and
manual deletion procedures for inbox payloads, messages, drafts, requests, sessions and backups;
no automatic retention policy is assumed.

## Validation

```bash
cd webapp/backend
python -m scripts.run_tests
cd ../frontend
npm run build
npm run test:render
```

The test runner uses uvloop when installed (included by `uvicorn[standard]` on Linux); this also
avoids restricted-environment asyncio thread-wakeup problems. The suite includes the ported Nouba
conversation acceptance tests and target migration, provider, authentication, authorization,
inventory, webhook/inbox, audio, employment and SPA-route regressions. Provider transports and
WhatsApp sends are mocked. A real Meta test-number exchange and live OpenAI/Gemini/Ollama/audio check
still require configured credentials and network access.

## No reply to a WhatsApp test message

The launcher starts the local app and, by default, ngrok pointing to port 8000. The full callback URL is stored in your Meta app's webhook
configuration; the repository only defines `/webhook/whatsapp` and a `YOUR_HOST` placeholder.
The original Hakathon launcher had an explicit `--ngrok` option, so stopping that launcher may
also have stopped its tunnel.

Run this read-only diagnostic from `webapp/backend`:

```bash
.venv/bin/python -m scripts.check_webhook
# Once you know the configured public callback URL:
.venv/bin/python -m scripts.check_webhook --url https://YOUR_HOST/webhook/whatsapp
```

It reports stored-event counts and active ngrok routing without showing messages or credentials.
The optional public probe checks that the public host reaches this integrated backend.
Restart the backend after logging changes. Safe console events now show `webhook.received`,
`webhook.parsed` with a message count, inbox processing, understanding and reply outcomes.
A POST returning 403 means signature validation failed; a message count of zero can be a
status-only event. If there is no inbound POST at all, check public routing and Meta subscriptions.
Send an actual WhatsApp message from your personal phone to the business test number; an
outgoing API test message is not itself an incoming user conversation.

### Restart and WhatsApp tunnel

Run `./start.sh --restart` to stop verified backend processes before starting.
Use `./start.sh --dev --restart` to also restart the development frontend.
Restart allows 15 seconds for graceful shutdown, then kills only surviving
processes from the verified project tree, checking PID identity before signaling.
Development-mode Ctrl+C shuts down both managed process groups, with a five-second
grace period before forced cleanup. Use Ctrl+C to stop; Ctrl+Z suspends processes.

The launcher starts `ngrok http 8000` automatically and prints the complete
WhatsApp callback URL. Install ngrok and configure its authentication first.
A matching existing tunnel is reused and left running on shutdown; a tunnel
started by the launcher stops with the app. Use `--no-ngrok` for local-only
startup or a separately managed public address. Meta settings are not changed:
copy the printed callback into Meta whenever the public URL changes.

Public email contacts currently require Latin characters. Mixed-script speech
transcriptions must be corrected with the exact written address, rather than
transliterated automatically.

### Original MACHINATI pages and algorithm

The earlier catalogue recreation has been replaced. The application now uses the
original MACHINATI catalogue, cooperative and operations HTML documents, including
their original embedded CSS and imagery, in isolated frames like the source app.
The operations request tab uses the original React RequestsDashboard. The source
page CSS is checked byte-for-byte against recorded SHA-256 hashes.

Normal runtime is self-contained. Generated original pages live in
`frontend/public/assets/machinati`; `backend/scripts/sync_machinati_pages.py` can
explicitly resync them from a chosen MACHINATI checkout. No source checkout is
needed to build or run the integrated app.

`/cooperative`, `/operations` and `/requests` require a valid authenticated session
before mounting their private views. Embedded private documents also verify the
session. API authorization remains enforced independently. The adapter only sends
the token to same-origin API endpoints, and tokens never enter URLs.

Integration fixes preserve original styling: target the configured business
WhatsApp number, repair mobile-menu toggling, use hourly estimates, exclude
owner-use reservations from availability summaries, use server-provided machine
candidates, clear stale selection when filters return no requests, and expose
existing inventory management. Completed request actions are retained.

The source algorithm proposes request priority and equipment candidates. It does
not optimize geographical travel routes or create a conflict-free usage schedule.
Its original weights are retained: normal 0 / urgent 25 / critical 40, verified
urgency +10, explicit date window +5, local machine fit +15 / transport review +5,
and waiting age up to +10. Ranked requests are reviewed by an operator before
approval. Frozen reference tests verify 144 score and 48 compatibility scenarios
against outputs from the original MACHINATI implementation. Alias normalization
is retained for Darija/French inventory and locality names.

Run `npm run test:catalogue` in `frontend` for source-style preservation, original
script syntax, authentication gates, token handling and integration regressions.
Browser visual verification is still pending in this restricted environment;
see `CATALOGUE_QA.md` for the manual checklist.
