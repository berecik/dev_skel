#!/usr/bin/env bash
set -euo pipefail

SKEL_DIR="${1:?skel_dir missing}"
TARGET_DIR="${2:?target_dir missing}"

echo "Merging additional files from $SKEL_DIR to $TARGET_DIR (FastAPI)..."

while IFS= read -r -d '' src; do
  rel="${src#"$SKEL_DIR"}"
  case "$rel" in
    */Makefile|*/merge.sh)
      continue ;;
  esac
  dst="$TARGET_DIR/$rel"
  if [[ ! -f "$dst" ]]; then
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
    echo "  + $rel"
  fi
done < <(find "$SKEL_DIR" -type f -print0)

echo "Done."
