#!/usr/bin/env bash
# Ubuntu 24.04 deployment. Run as the non-root account owning the checkout.
set -euo pipefail

install_system=false
ingest_docs=false
for arg in "$@"; do
  case "$arg" in
    --install-system) install_system=true ;;
    --ingest-docs) ingest_docs=true ;;
    --help|-h)
      echo 'Usage: bash scripts/deploy.sh [--install-system] [--ingest-docs]'
      echo 'Run inside the server checkout as a non-root sudo-capable user.'
      echo 'Requires a configured .env. Stops existing app services during deployment.'
      exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [[ $(uname -s) != Linux || $(id -u) == 0 ]]; then
  echo 'Run on the Ubuntu server as a non-root sudo-capable user.' >&2
  exit 1
fi
app_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# Restrict paths because systemd service values have their own escaping rules.
if [[ ! "$app_dir" =~ ^/[a-zA-Z0-9_./-]+$ ]]; then
  echo 'Checkout path must not contain spaces or special characters.' >&2; exit 1
fi
cd "$app_dir"
if [[ ! -f .env ]]; then
  echo 'Create the server .env from .env.example and configure credentials first.' >&2
  exit 1
fi
chmod 600 .env
sudo -n -v
if $install_system; then
  . /etc/os-release
  if [[ "$ID" != ubuntu || "$VERSION_ID" != 24.04 ]]; then
    echo '--install-system supports Ubuntu 24.04 only.' >&2; exit 1
  fi
  sudo apt-get update
  sudo apt-get install -y python3 python3-venv python3-pip docker.io docker-compose-v2
  sudo systemctl enable --now docker
fi
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"'
sudo docker compose version
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
# Parse .env as configuration, never execute it as shell code.
venv/bin/python - <<'PY'
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from app.config import settings
values = dotenv_values('.env')
password = values.get('POSTGRES_PASSWORD', '')
if not password or password == 'postgres':
    raise SystemExit('Set a non-default POSTGRES_PASSWORD in the server .env.')
url = make_url(settings.database_url)
if (url.drivername != 'postgresql+psycopg' or url.host not in ('localhost', '127.0.0.1')
        or url.port not in (None, 5432) or url.database != 'memorypalace'
        or url.username != 'postgres' or url.password != password):
    raise SystemExit('DATABASE_URL must match the local deployment database and POSTGRES_PASSWORD.')
if settings.api_base_url != 'http://127.0.0.1:8000':
    raise SystemExit('Set API_BASE_URL=http://127.0.0.1:8000 on the server.')
required = [settings.anthropic_api_key, settings.telegram_bot_token,
            settings.gemini_api_key if settings.embedding_provider == 'gemini' else settings.openai_api_key]
if not all(value.strip() for value in required) or not settings.telegram_owner_id:
    raise SystemExit('Configure provider credentials, bot token, and Telegram owner ID.')
print('Server configuration validated (values hidden).')
PY

# Pause app processes before migrations. On failure, leave them stopped for inspection.
for service in memorypalace-api memorypalace-bot; do
  if sudo systemctl cat "$service" >/dev/null 2>&1; then
    sudo systemctl stop "$service"
  fi
done
sudo docker compose --project-name memorypalace --env-file .env -f deploy/compose.yml up -d --wait --wait-timeout 120
venv/bin/alembic upgrade head
if $ingest_docs; then
  venv/bin/python -m scripts.ingest docs
fi
app_user=$(id -un)
app_group=$(id -gn)
for component in api bot; do
  if [[ "$component" == api ]]; then
    command="$app_dir/venv/bin/uvicorn app.api.main:app --host 127.0.0.1 --port 8000"
    dependencies=''
    after='network-online.target docker.service'
  else
    command="$app_dir/venv/bin/python -m bot.telegram_bot"
    dependencies='Requires=memorypalace-api.service'
    after='network-online.target docker.service memorypalace-api.service'
  fi
  sudo tee "/etc/systemd/system/memorypalace-$component.service" >/dev/null <<UNIT
[Unit]
Description=MemoryPalace $component
Wants=network-online.target
After=$after
$dependencies

[Service]
Type=simple
User=$app_user
Group=$app_group
WorkingDirectory=$app_dir
ExecStart=$command
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
UNIT

done
sudo systemctl daemon-reload
sudo systemctl enable --now memorypalace-api
venv/bin/python - <<'PY'
import time
import httpx
for attempt in range(30):
    try:
        response = httpx.get('http://127.0.0.1:8000/openapi.json', timeout=2)
        response.raise_for_status()
        break
    except httpx.HTTPError:
        time.sleep(1)
else:
    raise SystemExit('API did not become ready. Check journalctl -u memorypalace-api.')
PY
sudo systemctl enable --now memorypalace-bot
sudo systemctl is-active memorypalace-api memorypalace-bot
echo 'Services started. Verify a Telegram question, then reboot and verify again.'
echo 'Logs: sudo journalctl -u memorypalace-api -u memorypalace-bot -f'
