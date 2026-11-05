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

## Manual applications, document review and dispatch

Open `/apply` (also linked in the main navigation) to submit a machinery or personnel
request without WhatsApp. Save the request number and private tracking code shown
on submission. They allow tracking, PDF/JPEG/PNG uploads (5 MB each, 10 per request),
and supplementary information from any device. The code is a private access credential;
it cannot be recovered from a phone number. Uploaded documents are stored in SQLite,
so include the database in backups and allow for its increased size.

Administrators use `/requests` to inspect documents, record acceptance or refusal,
request additional information/documents with a message, and approve or refuse requests.
Operators can read the list but cannot make these decisions or download documents.
All supplied documents must be accepted before approval. Document acceptance records
human review; the application does not certify authenticity or verify issuing authorities.
Applicants see review messages by refreshing their tracking page; this flow does not
send WhatsApp notifications.

Approval dispatches a real (non-demo), local, compatible resource if available, or marks
the approved request as waiting on the priority list. Machines must satisfy the existing
type/location/date rules. Personnel must have an active non-demo worker listing with
the same normalized location and work/skill. Remote matches require coordination and
are not automatically assigned. A resource is held exclusively until the assigned request
is completed or cancelled; future dates do not permit overlapping reservations in this
initial workflow. Completion/cancellation releases the resource and dispatches the queue.
Machine inventory edits, worker publication/moderation and the admin queue retry button
also trigger dispatch, ordered by priority score and then oldest request. Allocations
record an assignment for cooperative coordination, not an external booking or notification.

Restart the backend to apply migration 005 automatically, and rebuild the frontend with
`npm run build` (or use the standard launcher). This workflow is independent of the Meta
webhook URL and can be tested on each developer's clone.

### Client and administrator responsibilities

Clients enter their own details on `/apply` or through the WhatsApp conversation.
The administrator dashboard contains the request list and review actions, not a
client submission form. Website applicants upload documents from their private
tracking page. WhatsApp applicants can send a PDF, JPEG or PNG after confirming a
request; include `#REQUEST_ID` in the document/photo caption when there is more
than one pending request. Attachments are associated only with requests whose
phone matches the Meta sender, and enter the same administrator review queue.

Clients can send `status`, `statut`, `mes demandes`, `طلباتي` or `حالة طلبي` on
WhatsApp to see their recent requests and outstanding requests for information.
Reply with the requested information (include `#REQUEST_ID` if multiple requests
need information). Website and WhatsApp attachments share the same file limits.
Receiving documents or extra information never approves a request automatically.
These inbound exchanges still require the configured Meta callback to reach the
backend; the website submission flow remains independent of it.

Uploaded document/image contents are never passed to an AI model, OCR service or
transcription service. The application stores filenames and attachments and checks
only supported file signatures and size limits. The administrator examines the
contents and records a human assessment of authenticity.

### AI-first conversation

`CONVERSATION_ROUTING=model_first` is the default. Each conversational free-text
turn (including transcribed audio) is sent to the configured understanding model
with the active draft and conversation context. The model extracts structured
intent and facts; application code validates them and performs database actions.
If understanding fails, deterministic parsing remains available as a fallback.
Logs show `dialogue.route` with `model` for successful AI understanding and
`fallback` when rules handle a failed model call. Navigation, explicit confirmations,
buttons, status queries, supplemental review information and document uploads keep
their dedicated handling. Documents and images never go to the model.

AI-first routing improves language interpretation but adds inference latency and
provider usage. Its timeout still uses `CONVERSATION_TIMEOUT_SECONDS`. Set
`CONVERSATION_ROUTING=rules_first` to restore the previous routing. Restart the
backend after changing the environment.

### Stopping the launcher

Use **Ctrl+C** to shut down the backend, development frontend, and any tunnel
started by this launcher. Ctrl+Z now also requests shutdown, rather than suspending
the launcher while its isolated servers keep running. For a launcher suspended
before this change, run `fg` in its original terminal, then press Ctrl+C.
`./start.sh --restart` still stops only verified project servers. Its port check
allows recently closed connections to expire naturally, while rejecting an
actual listener on the port.

### AI timeouts and document questions

`POST /webhook/whatsapp` returning 200 acknowledges delivery to the inbox. It does
not establish that AI understanding succeeded. `GET /api/machines` is website
inventory polling; webhook events with zero messages need no model processing.
`dialogue.understanding` with `conversation_timeout` means the understanding
deadline expired. Check the active provider independently with synthetic text:

```bash
cd backend
.venv/bin/python -m scripts.check_ai --timeout 8
```

The diagnostic reports provider/model, duration and a safe error code; it creates
no requests and sends no WhatsApp messages. Run it in your normal terminal with
network access. Connection failures/timeouts are distinguished from response
errors. OpenAI connections have a five-second connection timeout; the full
understanding deadline still follows `CONVERSATION_TIMEOUT_SECONDS`.

Questions such as `واش خصني شي وثيقة ؟` receive application document guidance
immediately, including outstanding administrator instructions for the sender.
This does not alter the draft or invent required documents. AI timeout replies
retain the current request summary or pending field instead of resetting to a
welcome menu.

### Conversational reply wording

With `CONVERSATION_REPLY_STYLE=model` (default with model-first routing), the
configured model phrases eligible conversational replies after the application
has determined the actual outcome. It receives the verified answer, recent text
turns, current task and last search. Attachments are never included. Exact
confirmation summaries, record listings and menus retain their original text.
Reply writing cannot change requests, approval, searches or resource allocation.
It has a separate four-second deadline (`CONVERSATION_REPLY_TIMEOUT_SECONDS`);
failure retains the verified answer. This adds a short model call and provider
usage. `CONVERSATION_REPLY_STYLE=template` restores fixed wording. Diagnostics
show `dialogue.reply_writing` and `dialogue.reply_writing_fallback`.

Short place follow-ups retain the last worker/job search goal. Changing places
with identical empty results no longer triggers the repeated-answer escape
message. Advert creation buttons appear on an advert offer, rather than on
subsequent unrelated questions. Clients searching workers/jobs do not need to
send arbitrary documents; administrators can request evidence for a submitted
request when needed.

### Initial checklist and administrator WhatsApp notifications

Migration 006 adds a durable outbound queue. Confirmed WhatsApp machinery requests
receive an initial example checklist with their request number. Website clients see
the same checklist in tracking and can opt into WhatsApp updates. `DOCUMENT_CHECKLIST`
is a semicolon-separated editable list: the defaults are an example service-request
summary, statement of work/location, cooperative representation evidence if applicable,
and land-use evidence for machinery if applicable. These are illustrative cooperative
examples, not a declaration of Moroccan legal requirements. No identity document is
mandatory by default and no document content is analyzed by AI.

When an administrator requests more information, the exact instructions and request
number are queued for WhatsApp. Clients can reply with text or attach documents to
that request. The admin view shows queued, sending, accepted by Meta, waiting for
client, or failed. Meta acceptance is not proof of delivery. Transient failures retry
up to five times, and admins can retry a failed notification. Unsent older instructions
are superseded when a newer document request is saved.

Free-text updates are sent while the client's WhatsApp service window is open.
Outside that window, configure `WHATSAPP_DOCUMENT_TEMPLATE` to the name of an
approved Meta template with two body parameters (request number and update text),
and `WHATSAPP_TEMPLATE_LANGUAGE` to its approved language. Without an approved
template, the queue displays `waiting_for_client` and resumes when the client sends
another message; it never claims an unsent update was sent. Template approval must
be completed in Meta, not in the local app. Existing separate ngrok behavior is unchanged.

### Public presentation without login

Set `PUBLIC_DEMO_MODE=true` in `backend/.env` and restart the backend. All visitors
can open operator/admin webpages and use their administration actions without a
login, including through the ngrok link. The navigation displays “Démonstration
publique” and hides logout. Set `PUBLIC_DEMO_MODE=false` and restart to restore
normal authentication. Credentials and existing accounts are retained.
