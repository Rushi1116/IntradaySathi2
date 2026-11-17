#!/usr/bin/env bash
cd "$(dirname "$0")"
pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env
if [ -n "$CODESPACE_NAME" ]; then
  (sleep 10; gh codespace ports visibility 8000:public -c "$CODESPACE_NAME" >/dev/null 2>&1
   echo "=== BACKEND URL (paste in app Settings): https://${CODESPACE_NAME}-8000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}/ ===") &
fi
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
