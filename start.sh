#!/usr/bin/env bash
# One backend process serves the WhatsApp bot, APIs and compiled React pages.
set -Eeuo pipefail

# Treat the terminal's suspend key as shutdown: managed servers run in separate
# sessions and would otherwise keep serving after the launcher was suspended.
suspend_shutdown() {
  printf '\nCtrl+Z received: stopping the app. Use Ctrl+C for normal shutdown.\n' >&2
  exit 148
}
trap suspend_shutdown TSTP

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MODE=compiled
CHECK_ONLY=false
BUILD=true
FORCE_INSTALL=false
RESTART=false
TUNNEL=true

usage() {
  cat <<'HELP'
Usage: ./start.sh [--dev | --no-build] [--install] [--restart] [--no-ngrok] [--check]

Default       Build the webpages and serve pages + API + WhatsApp on port 8000.
--dev         Run the API on 8000 and Vite with hot reload on 5173.
--no-build    Serve the existing frontend/dist bundle; Node/npm are not needed.
--install     Install pinned Python and frontend dependencies even if present.
--restart     Stop verified webapp processes (force after 15s), then restart.
--no-ngrok    Skip the automatic ngrok tunnel.
--check       Check local prerequisites/configuration; do not install or start servers.
--help        Show this help.

WEBAPP_PYTHON=/path/to/python selects an existing Python environment.
Otherwise backend/.venv is created automatically when necessary.
By default, ngrok http 8000 runs alongside the app (ngrok must be configured).
The full callback URL is printed; Meta settings are not changed.
HELP
}

for argument in "$@"; do
  case "$argument" in
    --dev) MODE=dev ;;
    --no-build) BUILD=false ;;
    --install) FORCE_INSTALL=true ;;
    --restart) RESTART=true ;;
    --no-ngrok) TUNNEL=false ;;
    --check) CHECK_ONLY=true ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$argument" >&2; usage >&2; exit 2 ;;
  esac
done
if [[ "$MODE" == dev && "$BUILD" == false ]]; then
  printf '%s\n' '--dev and --no-build cannot be combined.' >&2
  exit 2
fi

PYTHON_BIN="${WEBAPP_PYTHON:-$APP_DIR/backend/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  if [[ -n "${WEBAPP_PYTHON:-}" || "$CHECK_ONLY" == true ]]; then
    printf 'Python environment unavailable: %s\nRun without --check to create backend/.venv, or set WEBAPP_PYTHON.\n' "$PYTHON_BIN" >&2
    exit 1
  fi
  command -v python3 >/dev/null || { printf 'Install Python 3.12+ first.\n' >&2; exit 1; }
  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' || {
    printf 'Python 3.12+ is required.\n' >&2; exit 1;
  }
  printf 'Creating backend/.venv...\n'
  python3 -m venv "$APP_DIR/backend/.venv"
fi
PYTHON_BIN="$("$PYTHON_BIN" -c 'import sys; print(sys.executable)')"
"$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' || {
  printf 'Python 3.12+ is required.\n' >&2; exit 1;
}
if ! "$PYTHON_BIN" -c 'import fastapi,uvicorn,dotenv,httpx,pydantic,google.genai,multipart' >/dev/null 2>&1 || [[ "$FORCE_INSTALL" == true ]]; then
  if [[ "$CHECK_ONLY" == true ]]; then
    printf 'Backend dependencies need installation. Run ./start.sh --install.\n' >&2
    exit 1
  fi
  printf 'Installing pinned backend dependencies...\n'
  "$PYTHON_BIN" -m pip install -r "$APP_DIR/backend/requirements.lock.txt"
fi

if [[ ! -f "$APP_DIR/backend/.env" ]]; then
  if [[ "$CHECK_ONLY" == true ]]; then
    printf 'backend/.env is absent; normal startup will create it from .env.example.\n'
  else
    (umask 077; cp -n -- "$APP_DIR/backend/.env.example" "$APP_DIR/backend/.env")
    printf 'Created backend/.env. Add credentials there to enable live WhatsApp/AI.\n'
  fi
fi

if [[ "$BUILD" == true ]]; then
  command -v node >/dev/null && command -v npm >/dev/null || {
    printf 'Install Node.js 18+ and npm, or use --no-build with an existing bundle.\n' >&2; exit 1;
  }
  node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 18 ? 0 : 1)' || {
    printf 'Node.js 18+ is required.\n' >&2; exit 1;
  }
  if [[ ! -x "$APP_DIR/frontend/node_modules/.bin/vite" || ! -x "$APP_DIR/frontend/node_modules/.bin/tsc" || "$FORCE_INSTALL" == true ]]; then
    if [[ "$CHECK_ONLY" == true ]]; then
      printf 'Frontend dependencies need installation. Run ./start.sh --install.\n' >&2; exit 1
    fi
    printf 'Installing pinned frontend dependencies...\n'
    (cd "$APP_DIR/frontend"; npm ci --no-audit --no-fund)
  fi
elif [[ ! -f "$APP_DIR/frontend/dist/index.html" ]]; then
  printf 'No frontend bundle found. Run ./start.sh once without --no-build.\n' >&2
  exit 1
fi

# Only missing setting names are printed. Never source .env as shell code.
printf '\nWhatsApp configuration check:\n'
if ! (cd "$APP_DIR/backend"; "$PYTHON_BIN" -m scripts.check_config --mode whatsapp-voice); then
  printf 'These settings need attention for live WhatsApp. Webpages can still start.\n'
fi
printf '\nDashboard login check:\n'
if ! (cd "$APP_DIR/backend"; "$PYTHON_BIN" -m scripts.check_config --mode dashboard); then
  printf 'Public pages and the bot do not require an operator account. Private dashboard pages do.\n'
fi
if [[ "$CHECK_ONLY" == true ]]; then
  printf '\nLocal prerequisite check finished. No servers started or dependencies installed.\n'
  exit 0
fi

command -v setsid >/dev/null || { printf 'Startup requires the setsid utility.\n' >&2; exit 1; }
if [[ "$TUNNEL" == true ]]; then
  command -v ngrok >/dev/null || {
    printf 'Install and configure ngrok, or use --no-ngrok for local-only startup.\n' >&2
    exit 1
  }
fi

# Finish a requested frontend build before interrupting the running app.
if [[ "$RESTART" == true ]]; then
  if [[ "$MODE" == compiled && "$BUILD" == true ]]; then
    (cd "$APP_DIR/frontend"; npm run build)
    BUILD=false
  fi
  RESTART_ARGS=(--root "$APP_DIR")
  if [[ "$MODE" == dev ]]; then RESTART_ARGS+=(--frontend); fi
  (cd "$APP_DIR/backend"; "$PYTHON_BIN" -m scripts.restart_servers "${RESTART_ARGS[@]}")
fi

PORTS=(8000)
if [[ "$MODE" == dev ]]; then
  PORTS+=(5173)
fi
"$PYTHON_BIN" - "${PORTS[@]}" <<'PY'
import errno,socket,sys
for port in map(int,sys.argv[1:]):
    try:
        with socket.socket() as probe:
            # Uvicorn reuses its address too. Recently closed connections must
            # not be mistaken for a still-running listener during restart.
            probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            probe.bind(('127.0.0.1',port))
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            print(f'Port {port} is already occupied. Stop the old service before starting this app.',file=sys.stderr)
            print(f'Identify it with: lsof -nP -iTCP:{port} -sTCP:LISTEN',file=sys.stderr)
            print('For an existing webapp server, rerun with --restart. Unrelated services are never stopped automatically.',file=sys.stderr)
        elif exc.errno in (errno.EPERM,errno.EACCES):
            print(f'The operating system denied socket access for port {port}. This does not establish that the port is occupied.',file=sys.stderr)
            print('Run the launcher from your normal local terminal with network access.',file=sys.stderr)
        else:
            print(f'Cannot bind port {port}: {exc.strerror}',file=sys.stderr)
        sys.exit(1)
PY

if [[ "$MODE" == compiled && "$BUILD" == true ]]; then
  (cd "$APP_DIR/frontend"; npm run build)
fi

# Isolated process groups include npm/Vite and Uvicorn reload subprocesses.
CHILDREN=()
NGROK_LOG=""
cleanup() {
  trap - EXIT INT TERM TSTP
  for pid in "${CHILDREN[@]}"; do
    kill -TERM -- "-$pid" 2>/dev/null || true
    kill -CONT -- "-$pid" 2>/dev/null || true
  done
  # Bound shutdown even when a reloader or worker ignores termination.
  for ((attempt=0; attempt<50; attempt++)); do
    alive=false
    for pid in "${CHILDREN[@]}"; do
      if kill -0 -- "-$pid" 2>/dev/null; then alive=true; fi
    done
    if [[ "$alive" == false ]]; then break; fi
    sleep 0.1
  done
  for pid in "${CHILDREN[@]}"; do kill -KILL -- "-$pid" 2>/dev/null || true; done
  for pid in "${CHILDREN[@]}"; do wait "$pid" 2>/dev/null || true; done
  if [[ -n "$NGROK_LOG" ]]; then rm -f -- "$NGROK_LOG"; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if [[ "$MODE" == dev ]]; then
  (cd "$APP_DIR/backend"; exec setsid "$PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload) &
else
  (cd "$APP_DIR/backend"; exec setsid "$PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1) &
fi
CHILDREN+=("$!")
if [[ "$MODE" == dev ]]; then
  (cd "$APP_DIR/frontend"; exec setsid npm run dev -- --host 127.0.0.1 --port 5173 --strictPort) &
  CHILDREN+=("$!")
  printf 'Webpages: http://localhost:5173\n'
else
  printf 'Webpages: http://localhost:8000\n'
fi
printf 'Backend/webhook: http://localhost:8000\n'

if [[ "$TUNNEL" == true ]]; then
  tunnel_url() {
    (cd "$APP_DIR/backend"; "$PYTHON_BIN" -m scripts.ngrok_url)
  }
  if CALLBACK_BASE="$(tunnel_url)"; then
    printf 'Reusing existing ngrok tunnel.\n'
  else
    TUNNEL_STATUS=$?
    if [[ "$TUNNEL_STATUS" == 2 ]]; then
      printf 'An ngrok agent is already running without an HTTPS tunnel to port 8000. Configure it or use --no-ngrok.\n' >&2
      exit 1
    fi
    NGROK_LOG="$(mktemp)"
    setsid ngrok http 8000 --log stdout >"$NGROK_LOG" 2>&1 &
    NGROK_PID=$!
    CHILDREN+=("$NGROK_PID")
    CALLBACK_BASE=""
    for ((attempt=0; attempt<30; attempt++)); do
      if CALLBACK_BASE="$(tunnel_url)"; then break; fi
      if ! kill -0 "$NGROK_PID" 2>/dev/null; then break; fi
      sleep 0.5
    done
    if [[ -z "$CALLBACK_BASE" ]]; then
      printf 'ngrok failed to expose port 8000. Check ngrok authentication/configuration.\n' >&2
      printf 'Run ngrok http 8000 separately to see its diagnostic output.\n' >&2
      exit 1
    fi
  fi
  printf '\nWhatsApp callback URL: %s/webhook/whatsapp\n' "$CALLBACK_BASE"
  printf 'Use this URL in Meta if it differs from your current callback.\n'
fi
printf 'Press Ctrl+C to stop the app and any tunnel started by this launcher. Ctrl+Z also shuts it down.\n'
set +e
wait -n "${CHILDREN[@]}"
STATUS=$?
set -e
printf 'A service stopped; shutting down managed services.\n' >&2
if [[ "$STATUS" == 0 ]]; then STATUS=1; fi
exit "$STATUS"
