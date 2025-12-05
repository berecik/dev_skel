#!/usr/bin/env bash
# Shared common configuration loader for skeletons
set -euo pipefail

COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Locate config files (lowest to highest precedence)
CFG_DEFAULT="$COMMON_DIR/common-config.default.json"
CFG_REPO_LOCAL="$COMMON_DIR/../.skelrc.json"
CFG_ROOT_REPO="$(cd "$COMMON_DIR/../.." && pwd)/.skelrc.json"
CFG_HOME="${HOME:-}/.skelrc.json"

# Render merged JSON using jq if available, otherwise node fallback
_merge_json() {
  if command -v jq >/dev/null 2>&1; then
    local files=()
    files+=("$CFG_DEFAULT")
    [[ -f "$CFG_REPO_LOCAL" ]] && files+=("$CFG_REPO_LOCAL")
    [[ -f "$CFG_ROOT_REPO" ]] && files+=("$CFG_ROOT_REPO")
    [[ -f "$CFG_HOME" ]] && files+=("$CFG_HOME")
    jq -s 'reduce .[] as $item ({}; . * $item)' "${files[@]}"
  else
    # Node fallback to deep-merge
    node -e '
      const fs = require("fs");
      const paths = [
        process.argv[2], process.argv[3], process.argv[4], process.argv[5]
      ].filter(Boolean).filter(p => { try { fs.accessSync(p); return true; } catch { return false; } });
      const deepMerge = (a,b) => {
        if (Array.isArray(a) && Array.isArray(b)) return b; // replace arrays
        if (a && typeof a === "object" && b && typeof b === "object") {
          const out = {...a};
          for (const k of Object.keys(b)) out[k] = deepMerge(out[k], b[k]);
          return out;
        }
        return b === undefined ? a : b;
      };
      const result = paths.reduce((acc,p) => deepMerge(acc, JSON.parse(fs.readFileSync(p,"utf8"))), {});
      process.stdout.write(JSON.stringify(result));
    ' "$CFG_DEFAULT" "$CFG_REPO_LOCAL" "$CFG_ROOT_REPO" "$CFG_HOME"
  fi
}

_CFG_JSON="$(_merge_json)"

# Helper to extract values by jq path (dot notation)
get_config() {
  local key="${1:?key required}"
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$_CFG_JSON" | jq -r ".${key} // empty"
  else
    node -e '
      const key = process.argv[1];
      const data = JSON.parse(require("fs").readFileSync(0, "utf8"));
      const get = (obj, path) => path.split(".").reduce((o,k)=> (o&&k in o)? o[k] : undefined, obj);
      const v = get(data, key);
      process.stdout.write(v == null ? "" : String(typeof v === "object" ? JSON.stringify(v) : v));
    ' "$key" <<<"$_CFG_JSON"
  fi
}

# Export common fields as env vars for convenience
export SKEL_PROJECT_NAME="${SKEL_PROJECT_NAME:-$(get_config project.name || true)}"
export SKEL_AUTHOR_NAME="${SKEL_AUTHOR_NAME:-$(get_config author.name || true)}"
export SKEL_AUTHOR_EMAIL="${SKEL_AUTHOR_EMAIL:-$(get_config author.email || true)}"
export SKEL_LICENSE="${SKEL_LICENSE:-$(get_config license || true)}"
export SKEL_ORG="${SKEL_ORG:-$(get_config org || true)}"
export SKEL_REPO="${SKEL_REPO:-$(get_config repo || true)}"
export SKEL_HOMEPAGE="${SKEL_HOMEPAGE:-$(get_config homepage || true)}"
export SKEL_BUGS_URL="${SKEL_BUGS_URL:-$(get_config bugs.url || true)}"
export SKEL_PM="${SKEL_PM:-$(get_config pm || true)}"
