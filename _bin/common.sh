#!/usr/bin/env bash
# Common configuration and helpers for dev_skel scripts

set -euo pipefail

# Try to resolve repository root, but prefer a relocatable default
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Default SKEL_DIR to $HOME/dev_skel to allow running scripts from any location
SKEL_DIR_DEFAULT="$HOME/dev_skel"

# Defaults (can be overridden by environment or by ~/.dev_skel.conf)
: "${SKEL_DIR:=${SKEL_DIR_DEFAULT}}"
: "${DEV_DIR:=$HOME/dev}"
: "${EXCLUDES_FILE:=${SKEL_DIR}/_bin/rsync-common-excludes.txt}"

# Dev sync defaults
: "${DEV_SYNC_DIR:=$HOME/dev_sync}"
# Remote destination, e.g. user@host
: "${SYNC_SSH_HOST:=}"
# Remote destination path, e.g. /home/user/dev_sync
: "${SYNC_DEST_DIR:=}"

# Optional local override config
USER_CONF="$HOME/.dev_skel.conf"
if [[ -f "$USER_CONF" ]]; then
  # shellcheck source=/dev/null
  . "$USER_CONF"
fi

# Helper to ensure a directory exists
ensure_dir() {
  local d="$1"
  if [[ ! -d "$d" ]]; then
    mkdir -p "$d"
  fi
}
