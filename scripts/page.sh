#!/usr/bin/env bash
# Fire the HappyRobot staging pager. Secrets live in gitignored .env.
# Usage: scripts/page.sh
#        scripts/page.sh '{"tipo_emergencia":"…","pautas":"…","nivel_gravedad":"crítico","nombre_contacto":"…"}'
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a

: "${HAPPYROBOT_HOOK_URL:?set HAPPYROBOT_HOOK_URL in .env}"
: "${HAPPYROBOT_API_KEY:?set HAPPYROBOT_API_KEY in .env}"

if [[ $# -ge 1 ]]; then
  PAYLOAD=$1
else
  PAYLOAD=$(python3 -c 'import json,os; print(json.dumps({
    "tipo_emergencia": "Aviso de emergencia",
    "pautas": "Revise el visor y confirme que ha entendido los pasos.",
    "nivel_gravedad": "crítico",
    "nombre_contacto": os.environ.get("ONCALL_NAME") or "",
  }))')
fi

curl -sS -X POST "$HAPPYROBOT_HOOK_URL" \
  -H "Authorization: Bearer $HAPPYROBOT_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"
echo
