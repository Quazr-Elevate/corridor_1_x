#!/usr/bin/env bash
#
# Cor1x end-to-end test runner — one command for the whole stack.
#
#   scripts/e2e.sh                 # everything: backend + frontend
#   scripts/e2e.sh backend         # pytest only (unit/API + journeys)
#   scripts/e2e.sh frontend        # Playwright only (boots its own stack)
#   scripts/e2e.sh checks          # typecheck + lint + next build only
#   scripts/e2e.sh --keep          # leave the servers running afterwards
#   scripts/e2e.sh --no-build      # reuse an existing frontend build
#   scripts/e2e.sh frontend -- --grep @market     # pass args to Playwright
#
# Scenario catalogue: docs/testing/SCENARIOS.md
#
# What it does: throwaway SQLite DB + storage dir, backend on :8001 with
# DEBUG=true (so the signup screen shows the emailed code), frontend built
# and served on :3100 proxying /api to that backend. Nothing touches
# backend/cor1x.db or any real service — email goes to an outbox directory
# and FX rates are static.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKEND_PORT="${E2E_BACKEND_PORT:-8001}"
FRONTEND_PORT="${E2E_FRONTEND_PORT:-3100}"
API_URL="http://127.0.0.1:${BACKEND_PORT}"
BASE_URL="http://127.0.0.1:${FRONTEND_PORT}"
ADMIN_EMAIL="e2e-admin@cor1x.test"
ADMIN_PASSWORD="e2e-admin-pass-123"

RUN_DIR="${E2E_RUN_DIR:-$ROOT/.e2e-run}"
VENV="$ROOT/backend/.venv"
PY="$VENV/bin/python"

SUITE="all"
KEEP=0
BUILD=1
PW_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    all|backend|frontend|checks) SUITE="$1"; shift ;;
    --keep) KEEP=1; shift ;;
    --no-build) BUILD=0; shift ;;
    --) shift; PW_ARGS=("$@"); break ;;
    -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) PW_ARGS+=("$1"); shift ;;
  esac
done

# ── output helpers ───────────────────────────────────────────────────
bold() { printf '\033[1m%s\033[0m\n' "$*"; }
step() { printf '\n\033[1;36m── %s\033[0m\n' "$*"; }
fail() { printf '\033[31m%s\033[0m\n' "$*"; }

declare -a RESULT_NAMES=()
declare -a RESULT_CODES=()
record() { RESULT_NAMES+=("$1"); RESULT_CODES+=("$2"); }

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  if [[ $KEEP -eq 1 ]]; then
    bold "Left running: backend $API_URL (pid $BACKEND_PID), frontend $BASE_URL (pid $FRONTEND_PID)"
    bold "Run dir: $RUN_DIR"
    return
  fi
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null
  [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null
  wait 2>/dev/null
}
trap cleanup EXIT

require_venv() {
  if [[ ! -x "$PY" ]]; then
    fail "No backend virtualenv at $VENV"
    echo "  cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt"
    exit 1
  fi
}

wait_for() {  # wait_for <url> <name> <seconds>
  local url="$1" name="$2" deadline=$((SECONDS + ${3:-90}))
  while (( SECONDS < deadline )); do
    if curl -fsS -o /dev/null "$url" 2>/dev/null; then return 0; fi
    sleep 1
  done
  fail "$name did not come up at $url"
  return 1
}

# ── the stack ────────────────────────────────────────────────────────

start_backend() {
  step "Starting backend on :$BACKEND_PORT (throwaway database)"
  rm -rf "$RUN_DIR"
  mkdir -p "$RUN_DIR/uploads" "$RUN_DIR/outbox" "$RUN_DIR/logs"

  local hash
  hash="$("$PY" -c "import bcrypt;print(bcrypt.hashpw(b'$ADMIN_PASSWORD', bcrypt.gensalt(rounds=4)).decode())")"

  # DEBUG=true: the signup screen shows the emailed code (that is how the
  # browser specs finish a real signup) and localhost origins are trusted.
  export DATABASE_URL="sqlite+aiosqlite:///$RUN_DIR/e2e.db"
  export DEBUG=true
  export SESSION_SECRET="e2e-session-secret-0123456789abcdef"
  export COOKIE_SECURE=false
  export CROSS_SITE_COOKIES=false
  export KYB_ENC_KEYS="1:$("$PY" -c 'import base64;print(base64.b64encode(b"k"*32).decode())')"
  export KYB_HASH_KEY="$("$PY" -c 'import base64;print(base64.b64encode(b"h"*32).decode())')"
  export ADMIN_EMAIL="$ADMIN_EMAIL"
  export ADMIN_PASSWORD_HASH="$hash"
  export EMAIL_PROVIDER=console
  export EMAIL_OUTBOX_DIR="$RUN_DIR/outbox"
  export SMS_PROVIDER=console
  export SMS_OUTBOX_DIR="$RUN_DIR/outbox/sms"
  export STORAGE_BACKEND=local
  export STORAGE_DIR="$RUN_DIR/uploads"
  export LOOKUPS_STUB=true
  export FX_ENABLED=false
  export FX_PROVIDERS=static
  export RATE_LIMIT_ENABLED=true
  export LOG_LEVEL=WARNING
  export CORS_ORIGINS="$BASE_URL,http://localhost:$FRONTEND_PORT"
  export FRONTEND_BASE_URL="$BASE_URL"

  # create_all + stamp head, then the reference rows the stamped-over data
  # migrations would have inserted (countries + KYB document types).
  ( cd "$ROOT/backend" \
      && "$PY" scripts/init_local_db.py --force >"$RUN_DIR/logs/db.log" 2>&1 \
      && "$PY" scripts/seed_reference_data.py >>"$RUN_DIR/logs/db.log" 2>&1 )
  if [[ $? -ne 0 ]]; then fail "Database setup failed — see $RUN_DIR/logs/db.log"; tail -20 "$RUN_DIR/logs/db.log"; exit 1; fi

  ( cd "$ROOT/backend" && "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" \
      >"$RUN_DIR/logs/backend.log" 2>&1 ) &
  BACKEND_PID=$!
  wait_for "$API_URL/health" backend 90 || { tail -30 "$RUN_DIR/logs/backend.log"; exit 1; }

  # Create the first super admin (signing in once bootstraps it).
  curl -fsS -o /dev/null -X POST "$API_URL/admin/login" -H 'content-type: application/json' \
    -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" \
    || { fail "Could not bootstrap the admin account"; exit 1; }
  bold "Backend ready at $API_URL"
}

build_frontend() {
  step "Building the frontend"
  ( cd "$ROOT/frontend" && API_PROXY_TARGET="$API_URL" npx next build >"$RUN_DIR/logs/build.log" 2>&1 )
  local code=$?
  if [[ $code -ne 0 ]]; then fail "next build failed — see $RUN_DIR/logs/build.log"; tail -40 "$RUN_DIR/logs/build.log"; fi
  return $code
}

start_frontend() {
  step "Starting the frontend on :$FRONTEND_PORT"
  ( cd "$ROOT/frontend" && API_PROXY_TARGET="$API_URL" npx next start -p "$FRONTEND_PORT" -H 127.0.0.1 \
      >"$RUN_DIR/logs/frontend.log" 2>&1 ) &
  FRONTEND_PID=$!
  wait_for "$BASE_URL/login" frontend 120 || { tail -30 "$RUN_DIR/logs/frontend.log"; return 1; }
  bold "Frontend ready at $BASE_URL"
}

# ── suites ───────────────────────────────────────────────────────────

run_backend_tests() {
  step "Backend — unit + API suite"
  ( cd "$ROOT/backend" && "$PY" -m pytest -q -m "not e2e" )
  record "backend unit/API (pytest -m 'not e2e')" $?

  step "Backend — end-to-end journeys"
  ( cd "$ROOT/backend" && "$PY" -m pytest -q tests/e2e )
  record "backend journeys (tests/e2e)" $?
}

run_checks() {
  step "Frontend — typecheck"
  ( cd "$ROOT/frontend" && npm run --silent typecheck )
  record "frontend typecheck" $?

  step "Frontend — lint"
  ( cd "$ROOT/frontend" && npm run --silent lint )
  record "frontend lint" $?
}

run_frontend_tests() {
  step "Frontend — Playwright browser journeys"
  ( cd "$ROOT/frontend" \
      && E2E_BASE_URL="$BASE_URL" \
         E2E_API_URL="$API_URL" \
         E2E_ADMIN_EMAIL="$ADMIN_EMAIL" \
         E2E_ADMIN_PASSWORD="$ADMIN_PASSWORD" \
         PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/opt/pw-browsers}" \
         npx playwright test "${PW_ARGS[@]+"${PW_ARGS[@]}"}" )
  record "frontend journeys (Playwright)" $?
}

# ── go ───────────────────────────────────────────────────────────────

require_venv
bold "Cor1x end-to-end run — suite: $SUITE"

case "$SUITE" in
  backend)
    run_backend_tests
    ;;
  checks)
    run_checks
    [[ $BUILD -eq 1 ]] && { start_backend; build_frontend; record "frontend build" $?; }
    ;;
  frontend)
    run_checks
    start_backend
    if [[ $BUILD -eq 1 ]]; then build_frontend; record "frontend build" $?; fi
    start_frontend && run_frontend_tests || record "frontend journeys (Playwright)" 1
    ;;
  all)
    run_backend_tests
    run_checks
    start_backend
    if [[ $BUILD -eq 1 ]]; then build_frontend; record "frontend build" $?; fi
    start_frontend && run_frontend_tests || record "frontend journeys (Playwright)" 1
    ;;
esac

# ── summary ──────────────────────────────────────────────────────────
printf '\n'
bold "════ Summary ════"
failed=0
for i in "${!RESULT_NAMES[@]}"; do
  if [[ "${RESULT_CODES[$i]}" -eq 0 ]]; then
    printf '  \033[32m✓ PASS\033[0m  %s\n' "${RESULT_NAMES[$i]}"
  else
    printf '  \033[31m✗ FAIL\033[0m  %s (exit %s)\n' "${RESULT_NAMES[$i]}" "${RESULT_CODES[$i]}"
    failed=1
  fi
done
printf '\n'
if [[ $failed -eq 0 ]]; then
  bold "Everything passed."
else
  fail "Something failed. Logs: $RUN_DIR/logs/ · Playwright report: frontend/e2e-results/html/index.html"
fi
exit $failed
