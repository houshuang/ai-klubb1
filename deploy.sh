#!/usr/bin/env bash
# Deploy Klubb1 Tivoli to Alif. Idempotent: safe to re-run after every change.
#   ./deploy.sh            sync web + backend, restart, health-check
#   ./deploy.sh --install  also (re)install systemd unit and nginx fragments
set -euo pipefail
cd "$(dirname "$0")"
HOST=${KLUBB1_HOST:-alif}

rsync -az --delete web/ "$HOST":/opt/klubb1/web/
rsync -az --exclude .venv --exclude __pycache__ --exclude data backend/ "$HOST":/opt/klubb1/backend/

ssh "$HOST" 'set -e
  cd /opt/klubb1/backend
  [ -d .venv ] || python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
  mkdir -p /opt/klubb1/data'

if [[ "${1:-}" == "--install" ]]; then
  scp -q deploy/klubb1.service "$HOST":/etc/systemd/system/klubb1.service
  scp -q deploy/nginx-klubb1.conf "$HOST":/etc/nginx/snippets/klubb1.conf
  scp -q deploy/klubb1-rate-limit.conf "$HOST":/etc/nginx/conf.d/klubb1-rate-limit.conf
  ssh "$HOST" 'set -e
    [ -f /etc/klubb1.env ] || { echo "Missing /etc/klubb1.env (see deploy/klubb1.env.example)"; exit 1; }
    chmod 600 /etc/klubb1.env
    SITE=/etc/nginx/sites-available/petrarca-expo-ssl
    grep -q "snippets/klubb1.conf" "$SITE" || {
      cp "$SITE" "$SITE.before-klubb1-$(date +%Y%m%dT%H%M%SZ)"
      sed -i "s#    include /etc/nginx/snippets/kaja.conf;#    include /etc/nginx/snippets/kaja.conf;\n    include /etc/nginx/snippets/klubb1.conf;#" "$SITE"
    }
    nginx -t
    systemctl reload nginx
    systemctl daemon-reload
    systemctl enable klubb1.service >/dev/null'
fi

ssh "$HOST" 'systemctl restart klubb1.service && sleep 2 && systemctl is-active klubb1.service'
curl -fsS https://alifstian.duckdns.org/klubb1/api/health | python3 -m json.tool
