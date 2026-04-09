# Tiny shell helpers used by every skeleton's bash `gen` script.
#
# Source this file with `. "$COMMON_DIR/slug.sh"` (where $COMMON_DIR is
# the per-skel `_skels/_common/` path) before reading the optional second
# positional arg, then pipe it through `slugify_service_name` so users can
# pass either a display name (`"Ticket Service"`) or an already-slugified
# value (`ticket_service`) without thinking about it.
#
# Mirrors `dev_skel_lib.slugify_service_name` in Python so the static
# `make gen-*` flow and the relocatable `_bin/skel-gen` flow produce
# identical on-disk service directory names.

slugify_service_name() {
  local raw="${1:-}"
  if [[ -z "$raw" ]]; then
    printf 'service'
    return 0
  fi
  # Replace any run of non-alphanumeric characters with a single
  # underscore, lowercase the result, and trim leading / trailing
  # underscores.
  local cleaned
  cleaned="$(printf '%s' "$raw" \
    | LC_ALL=C tr -c '[:alnum:]' '_' \
    | LC_ALL=C tr '[:upper:]' '[:lower:]' \
    | sed -E 's/_+/_/g; s/^_+//; s/_+$//')"
  if [[ -z "$cleaned" ]]; then
    printf 'service'
    return 0
  fi
  if [[ "${cleaned:0:1}" =~ [0-9] ]]; then
    cleaned="svc_${cleaned}"
  fi
  printf '%s' "$cleaned"
}
