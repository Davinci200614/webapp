# Integration implementation status

The original `hakathon` and `MACHINATI` repositories remain unchanged. All runtime dependencies,
source modules, migrations and React views required by the integration live inside `webapp`.
The root `INTEGRATION_REVIEW.md` describes the earlier incomplete state.

## Implemented coverage

| Capability | Integrated implementation |
|---|---|
| Nouba conversation | Original v2 controller and service orchestration, extraction, understanding, guided choices, contacts, locations and shared alias catalog |
| Machinery intake | Text/audio, contextual collection, relative dates, correction, cancellation/reset/resume, delivered-summary confirmation, restart continuity and message deduplication |
| Employment | Worker/job drafts, explicit contact consent, publication, owner listing/removal commands, searches, public web directory and operator withdrawal |
| AI providers | OpenAI or Gemini/auto understanding with explicit configured fallback, local Ollama, independent OpenAI/Gemini transcription and safe diagnostics |
| MACHINATI operations | Full priority rules, verified urgency bonus, explicit date-window bonus, availability-window overlap, ownership/own-use rules and canonical machine/location fit |
| Request APIs | Authenticated listing, status filtering, priority/fit explanations and matching equipment, JSON status updates plus query compatibility, urgency verification |
| Inventory | Public catalogue, authenticated full inventory view, admin create/edit of all operational fields |
| Pages | Catalogue, cooperative, operations, requests, inventory, employment, inspector, privacy, terms and data-deletion URLs; old HTML/query navigation aliases |
| Inspector | Authenticated, opt-in snapshot with transcripts/replies, drafts, listings, requests, equipment, catalog and durable-inbox inspection/retry |
| Authentication | Password hashes, expiring sessions, corrected timestamp comparison, role restoration, private-read authorization, role-aware UI and local account-provisioning command |
| Processing durability | Transactional inbox before acknowledgment, receipt ordering per phone, concurrent different phones, bounded retries, restart recovery and manual failed-message retry |
| Persistence | SQLite schema v4, transactional numbered migrations, installed catalog, online backup, explicit legacy import and clean-target restore |
| Demo data | Explicit seed command includes both Nouba's fictional employment/equipment and MACHINATI's priority scenarios without deleting legacy records |

## Validation and operational boundaries

- Frontend TypeScript compilation and production Vite build passed.
- Static React render smoke checks passed for all ten routes and five populated product views.
- All 129 backend tests passed after the launcher addition, including transport, strict schema,
  transcription, provider-routing, configuration and launcher lifecycle coverage. Regression coverage includes the ported Nouba conversation suite, MACHINATI priority
  tests, target APIs, provider transports, migrations, session/role behavior, audio transcript
  persistence, retry/concurrency behavior and signed webhook-to-operator-review flow.
- The signed flow uses mocked WhatsApp sends, processes a complete machinery conversation,
  replays its confirmation message, verifies a single resulting request with canonical local
  inventory fit, and approves/completes it through the authenticated operator API.
- Browser network smoke tests could not run because this execution environment denies network
  sockets. Static React rendering is not a substitute for an interactive browser test.
- No live Meta or AI-provider traffic was sent. Configure real credentials/models and perform a
  real WhatsApp text/audio/button exchange before changing the production callback.
- Use one backend process with SQLite. Durable inbox recovery and per-phone ownership are not
  designed for multiple Uvicorn workers or multiple application replicas.
- Outbound delivery is at least once. A crash between Meta accepting a reply and the local
  delivery commit may cause the same reply to be resent; cached domain results prevent repeating
  successful request publication during ordinary delivery retries.
- Source prototypes without working services remain outside implemented service coverage:
  IoT telemetry, cooperative verification, payments and guaranteed machine reservations.
  Cooperative introductions use a real WhatsApp handoff. Desired-date planning shows approved
  requests and does not claim a confirmed booking.
- Legal operator identity/contact and data-retention details still require deployment-owner
  values. The legal pages explicitly retain those placeholders.

Start pages and the WhatsApp backend together with `./webapp/start.sh` from the workspace root.
Use `--dev` for Vite hot reload; both development process groups stop together. Existing `.env`
values are preserved, and a public HTTPS tunnel is still configured separately.

Run `python -m scripts.run_tests` in `backend`, and `npm run build && npm run test:render` in
`frontend`. See [README.md](README.md) for startup, settings and access controls.
