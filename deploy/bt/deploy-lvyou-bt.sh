#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <source_dir|artifact.tar.gz> <git_sha>" >&2
  exit 64
fi

SOURCE_PATH="$1"
GIT_SHA="$2"

APP_ROOT="/www/wwwroot/ly.scf-stem.com"
APP_DIR="$APP_ROOT/app"
RELEASES_DIR="$APP_ROOT/releases"
VENV_PATH="/www/server/pyporject_evn/scf-stem.com_venv"
SERVICE_NAME="scf-ly.service"
HEALTH_URL="http://127.0.0.1:5002/"
GUNICORN_LOG="/www/wwwlogs/ly.scf-stem.com.gunicorn.log"
NGINX_CONF="/www/server/panel/vhost/nginx/python_ly.scf-stem.com.conf"

timestamp="$(date +%Y%m%d-%H%M%S)"
release_name="${timestamp}-${GIT_SHA:0:12}"
release_dir="$RELEASES_DIR/$release_name"
backup_dir="$APP_ROOT/app.prev-$release_name"
swapped=0

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "Missing required file: $path" >&2
    exit 1
  fi
}

require_input() {
  local path="$1"
  if [[ ! -f "$path" && ! -d "$path" ]]; then
    echo "Missing deploy input: $path" >&2
    exit 1
  fi
}

copy_if_exists() {
  local source_path="$1"
  local target_path="$2"

  if [[ -e "$source_path" ]]; then
    mkdir -p "$(dirname "$target_path")"
    cp -a "$source_path" "$target_path"
  fi
}

populate_release_dir() {
  local source_path="$1"
  local target_dir="$2"

  if [[ -d "$source_path" ]]; then
    command -v rsync >/dev/null
    rsync -a --delete "$source_path"/ "$target_dir"/
  elif [[ -f "$source_path" ]]; then
    tar -xzf "$source_path" -C "$target_dir"
  else
    echo "Unsupported deploy input: $source_path" >&2
    exit 1
  fi
}

write_release_marker() {
  local target_dir="$1"
  {
    echo "project=lvyou"
    echo "git_sha=$GIT_SHA"
    echo "deployed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "source_path=$SOURCE_PATH"
    echo "release_dir=$release_dir"
  } > "$target_dir/.deploy-release"
}

restart_service() {
  mkdir -p "$(dirname "$GUNICORN_LOG")"
  touch "$GUNICORN_LOG"
  chown www:www "$GUNICORN_LOG"
  chmod 664 "$GUNICORN_LOG"
  systemctl restart "$SERVICE_NAME"
  systemctl is-active --quiet "$SERVICE_NAME"
}

wait_for_current_app_process() {
  local pid line cwd
  for _ in $(seq 1 30); do
    pid="$(systemctl show -p MainPID --value "$SERVICE_NAME" 2>/dev/null || true)"
    if [[ "$pid" =~ ^[0-9]+$ ]] && [[ "$pid" -gt 0 ]]; then
      line="$(pwdx "$pid" 2>/dev/null || true)"
      cwd="${line#*: }"
      if [[ "$cwd" == "$APP_DIR" ]]; then
        return 0
      fi
    fi
    sleep 1
  done
  echo "$SERVICE_NAME did not start from $APP_DIR" >&2
  return 1
}

wait_for_http() {
  local url="$1"
  for _ in $(seq 1 30); do
    if curl -fsSI "$url" >/dev/null; then
      return 0
    fi
    sleep 1
  done
  return 1
}

update_nginx_version_header() {
  if [[ ! -f "$NGINX_CONF" ]]; then
    return 0
  fi

  cp -a "$NGINX_CONF" "$NGINX_CONF.bak-$release_name"
  if grep -q "add_header X-Version" "$NGINX_CONF"; then
    sed -i "s/add_header X-Version .*/add_header X-Version \"v-${GIT_SHA:0:7}\";/" "$NGINX_CONF"
  else
    sed -i "/proxy_cache off;/a\\        add_header X-Version \"v-${GIT_SHA:0:7}\";" "$NGINX_CONF"
  fi
  nginx -t
  systemctl reload nginx
}

rollback() {
  local exit_code="$1"

  if [[ "$exit_code" -eq 0 ]]; then
    return 0
  fi

  echo "Deploy failed. Rolling back lvyou release..." >&2
  systemctl status "$SERVICE_NAME" --no-pager -l >&2 || true
  journalctl -u "$SERVICE_NAME" -n 120 --no-pager >&2 || true
  if [[ -f "$GUNICORN_LOG" ]]; then
    tail -n 160 "$GUNICORN_LOG" >&2 || true
  fi

  if [[ "$swapped" -eq 1 ]]; then
    systemctl stop "$SERVICE_NAME" || true
    rm -rf "$APP_DIR"
    if [[ -d "$backup_dir" ]]; then
      mv "$backup_dir" "$APP_DIR"
      chown -R www:www "$APP_DIR"
      restart_service || true
      wait_for_current_app_process || true
      wait_for_http "$HEALTH_URL" || true
    fi
  else
    rm -rf "$release_dir"
    if ! systemctl is-active --quiet "$SERVICE_NAME"; then
      restart_service || true
      wait_for_current_app_process || true
      wait_for_http "$HEALTH_URL" || true
    fi
  fi
}

trap 'exit_code=$?; rollback "$exit_code"; exit "$exit_code"' EXIT

require_input "$SOURCE_PATH"
require_file "$VENV_PATH/bin/activate"

mkdir -p "$RELEASES_DIR"
rm -rf "$release_dir"
mkdir -p "$release_dir"
echo "Populating lvyou release from $SOURCE_PATH"
populate_release_dir "$SOURCE_PATH" "$release_dir"

copy_if_exists "$APP_DIR/.env" "$release_dir/.env"
copy_if_exists "$APP_DIR/.well-known" "$release_dir/.well-known"
write_release_marker "$release_dir"

chown -R www:www "$release_dir"

source "$VENV_PATH/bin/activate"
cd "$release_dir"
python -m pip install -r requirements.txt
if command -v node >/dev/null; then
  PYTHONPATH="$release_dir" python -m pytest -q
else
  PYTHONPATH="$release_dir" python -m pytest -q --ignore=tests/test_model_preview_format.py
fi

systemctl stop "$SERVICE_NAME"

if [[ -d "$APP_DIR" ]]; then
  mv "$APP_DIR" "$backup_dir"
  swapped=1
fi
mv "$release_dir" "$APP_DIR"
swapped=1
chown -R www:www "$APP_DIR"

restart_service
wait_for_current_app_process
wait_for_http "$HEALTH_URL"
update_nginx_version_header

trap - EXIT
echo "Lvyou deploy succeeded for $GIT_SHA"
