# Environment setup: OpenAI + WhatsApp

Put configuration in **`webapp/backend/.env`**, not the frontend directory. Start from
`.env.example`; no real key is included or generated. Restart the backend after changes.

## Minimal OpenAI configuration

Use these settings for OpenAI-only operation. Substitute the placeholder values locally:

```dotenv
APP_NAME=MACHINATI × Nouba
DB_PATH=webapp.db
CORS_ORIGINS=http://localhost:5173

META_VERIFY_TOKEN=your-own-random-verification-string
META_APP_SECRET=your-meta-app-secret
META_ACCESS_TOKEN=your-whatsapp-cloud-api-access-token
META_PHONE_NUMBER_ID=your-meta-phone-number-id
META_GRAPH_VERSION=v23.0
WHATSAPP_CONTACT_NUMBER=your-public-business-number-with-country-code

OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4.1-mini
OPENAI_STT_MODEL=gpt-4o-mini-transcribe
OPENAI_TIMEOUT_SECONDS=45
LLM_PROVIDER=openai
CONVERSATION_PROVIDER=openai
CONVERSATION_CORE=v2
CONVERSATION_ENABLED=true
CONVERSATION_MODEL=
CONVERSATION_TIMEOUT_SECONDS=15
STT_PROVIDER=openai
LLM_FALLBACK_PROVIDER=

AUTH_BOOTSTRAP_EMAIL=your-admin-email
AUTH_BOOTSTRAP_PASSWORD=your-unique-password-at-least-12-characters
AUTH_SESSION_TTL_HOURS=12
MUTATIONS_ENABLED=true
INSPECTOR_ENABLED=false
```

The models are configurable examples, not a claim about the newest or cheapest model or access
in your API project. Use a key/project with access to the selected text and transcription models.

## Which blank fields need values?

| Setting | Required for | Value |
|---|---|---|
| `AUTH_BOOTSTRAP_EMAIL` | First operator account | Your chosen login email; this does not send email or require SMTP |
| `AUTH_BOOTSTRAP_PASSWORD` | First operator account | A unique password of at least 12 characters |
| `OPENAI_API_KEY` | OpenAI text understanding and transcription | Your server-side OpenAI API project key |
| `OPENAI_MODEL` | OpenAI text understanding | Default `gpt-4.1-mini`; supports the structured understanding schema |
| `OPENAI_STT_MODEL` | WhatsApp voice notes | Default `gpt-4o-mini-transcribe`; separate from the text model |
| `META_VERIFY_TOKEN` | Meta webhook verification | A random secret string you choose and also configure in Meta |
| `META_APP_SECRET` | Validating incoming webhook signatures | The secret of your Meta app |
| `META_ACCESS_TOKEN` | Sending replies and downloading voice notes | A valid WhatsApp Cloud API token for the configured business/phone |
| `META_PHONE_NUMBER_ID` | Meta API send endpoint | Meta's internal ID for the phone; **not** the phone number |
| `WHATSAPP_CONTACT_NUMBER` | Public catalogue/directory handoff links | The actual business phone, including country code; digits only, e.g. `2126…` |

Leave `CONVERSATION_MODEL` blank to inherit `OPENAI_MODEL`. This override is only needed when
you deliberately choose a different model for the v2 controller.

For OpenAI-only operation you can leave all `GEMINI_*`, `CONVERSATION_GEMINI_MODEL`,
`OPERATOR_API_KEY`, `ADMIN_API_KEY`, and `OLLAMA_MODEL` values blank. Ollama settings are unused
when `LLM_FALLBACK_PROVIDER` is blank. Enable `LLM_FALLBACK_PROVIDER=ollama` only after running
Ollama and installing/configuring its model. Existing Gemini settings remain available if you
explicitly select it. `CONVERSATION_THINKING_LEVEL` only affects Gemini.

Do not leave numeric or boolean settings blank: retain the example defaults. Keep
`DB_PATH=webapp.db` unless deliberately selecting another database. Changing it points the app
at a different database and can make previous records/accounts appear absent.

After the administrator exists, remove the bootstrap password from the environment; existing
accounts remain usable. Set `INSPECTOR_ENABLED=true` only when you want the admin inspector.
The optional API-key fields are not needed for normal email/password login.

## Configuration is only part of setup

1. Run `./webapp/start.sh` from the workspace root. It installs missing dependencies, builds
   the pages and serves both the website and WhatsApp API on port 8000. Use `--dev` for
   frontend hot reload on port 5173. See [README.md](README.md).
2. For WhatsApp, expose the backend through a reachable HTTPS deployment or development tunnel.
   Meta's callback is `https://YOUR-BACKEND-HOST/webhook/whatsapp`. `localhost:8000` is not a
   callback reachable from Meta. Use the same verify-token value and subscribe to incoming
   message events in your Meta setup.
3. Make sure the Meta token, configured phone and test recipients/business setup permit the
   exchange. An invalid/expired token or a missing subscription is not fixed by the `.env` file.
4. Use an OpenAI API project with available usage/billing and access to the selected models.
   Model access and response quality need a live check; mocked tests do not establish them.
5. For a hosted frontend, change `CORS_ORIGINS` to its actual origin. For local Vite development,
   keep `http://localhost:5173`. If serving everything from the backend, open that backend URL.
6. Run one backend worker. Sign in, add a machine, and test text → confirmation → request review;
   then test a real Darija/French voice note and the confirmation/edit buttons.

Check required configuration without printing secrets:

```bash
cd webapp/backend
python -m scripts.check_config --mode whatsapp-voice
# Dashboard-only setup:
python -m scripts.check_config --mode dashboard
```

WhatsApp checks do not require dashboard bootstrap credentials or a public handoff number.
The dashboard check only requires bootstrap credentials when no operator account exists.
This check validates configuration presence and basic syntax. It does not contact providers,
validate model access/token permissions, verify a public callback, or spend API credits.

## Official API references

- [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini)
- [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Audio transcription API](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create)
