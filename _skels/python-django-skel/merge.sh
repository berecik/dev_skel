#!/usr/bin/env bash
set -euo pipefail

SKEL_DIR="${1:?skel_dir missing}"
TARGET_DIR="${2:?target_dir missing}"

echo "Merging additional files from $SKEL_DIR to $TARGET_DIR (Django)..."

exclude_generated() {
  local rel="$1"
  case "$rel" in
    */Makefile|*/merge.sh)
      return 0 ;;
    /manage.py)
      return 0 ;;
    /myproject/__init__.py|/myproject/asgi.py|/myproject/settings.py|/myproject/urls.py|/myproject/wsgi.py)
      return 0 ;;
  esac
  return 1
}

while IFS= read -r -d '' src; do
  rel="${src#"$SKEL_DIR"}"
  if exclude_generated "$rel"; then
    continue
  fi
  dst="$TARGET_DIR/$rel"
  if [[ ! -f "$dst" ]]; then
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
    echo "  + $rel"
  fi
done < <(find "$SKEL_DIR" -type f -print0)

echo "Done."
