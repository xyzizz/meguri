#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${MEGURI_REPO_URL:-https://github.com/xyzizz/meguri.git}"
PACKAGE_SPEC="${MEGURI_PACKAGE_SPEC:-git+${REPO_URL}}"
RUN_INIT=true
FORCE=false
OFFLINE=false

usage() {
  cat <<'USAGE'
Install Meguri for Codex and Claude Code.

Usage:
  curl -fsSL https://raw.githubusercontent.com/xyzizz/meguri/main/install.sh | bash

Agent-first install:
  Paste the prompt from prompts/install.md into Codex or Claude Code while the
  target project is open. The current AI agent will run this installer and then
  continue with the /meguri workflow. The installer refreshes official agent
  entrypoint templates first, then initializes the project pack.

Options:
  --init             Compatibility no-op; project initialization runs by default.
  --install-skills   Compatibility no-op; slash entrypoints are installed by default.
  --offline          Use bundled slash entrypoint templates during refresh.
  --force            Overwrite generated Meguri files during initialization.
  --repo-url URL     Install from a different Git repository URL.
  --package-spec S   Install an explicit pip package spec.
  -h, --help         Show this help.
USAGE
}

log() {
  printf 'meguri: %s\n' "$*"
}

die() {
  printf 'meguri: error: %s\n' "$*" >&2
  exit 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --init)
      RUN_INIT=true
      ;;
    --install-skills)
      RUN_INIT=true
      ;;
    --offline)
      OFFLINE=true
      ;;
    --force)
      FORCE=true
      ;;
    --repo-url)
      [ "$#" -ge 2 ] || die "--repo-url requires a value"
      REPO_URL="$2"
      PACKAGE_SPEC="git+${REPO_URL}"
      shift
      ;;
    --package-spec)
      [ "$#" -ge 2 ] || die "--package-spec requires a value"
      PACKAGE_SPEC="$2"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
  shift
done

command -v python3 >/dev/null 2>&1 || die "python3 is required"

PIPX_CMD=()
if command -v pipx >/dev/null 2>&1; then
  PIPX_CMD=(pipx)
elif python3 -m pipx --version >/dev/null 2>&1; then
  PIPX_CMD=(python3 -m pipx)
else
  log "pipx not found; installing pipx with python3 -m pip install --user pipx"
  python3 -m pip install --user pipx
  PIPX_CMD=(python3 -m pipx)
fi

log "installing ${PACKAGE_SPEC}"
PIPX_INSTALL_ARGS=(install --force)
if "${PIPX_CMD[@]}" install --help 2>/dev/null | grep -q -- '--backend'; then
  # Avoid broken pyenv/uv shims in agent terminals. pip is slower but steadier.
  PIPX_INSTALL_ARGS+=(--backend pip)
fi
PIPX_DEFAULT_BACKEND=pip "${PIPX_CMD[@]}" "${PIPX_INSTALL_ARGS[@]}" "${PACKAGE_SPEC}"
"${PIPX_CMD[@]}" ensurepath >/dev/null 2>&1 || true

resolve_meguri() {
  local pipx_bin_dir=""

  if command -v meguri >/dev/null 2>&1; then
    command -v meguri
    return 0
  fi

  pipx_bin_dir="$("${PIPX_CMD[@]}" environment --value PIPX_BIN_DIR 2>/dev/null || true)"
  for candidate in \
    "${pipx_bin_dir}/meguri" \
    "${HOME}/.local/bin/meguri" \
    "${HOME}/Library/Python/3.13/bin/meguri" \
    "${HOME}/Library/Python/3.12/bin/meguri" \
    "${HOME}/Library/Python/3.11/bin/meguri" \
    "${HOME}/Library/Python/3.10/bin/meguri"; do
    if [ -n "${candidate}" ] && [ -x "${candidate}" ]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  return 1
}

MEGURI_BIN="$(resolve_meguri)" || die "Meguri installed, but the executable was not found. Run: python3 -m pipx ensurepath"

log "installed: ${MEGURI_BIN}"

if [ "${RUN_INIT}" = true ]; then
  refresh_args=()
  if [ "${OFFLINE}" = true ]; then
    refresh_args+=(--offline)
  fi
  init_args=()
  if [ "${FORCE}" = true ]; then
    init_args+=(--force)
  fi
  log "refreshing Meguri entrypoints"
  "${MEGURI_BIN}" refresh "${refresh_args[@]}"
  log "initializing current project"
  "${MEGURI_BIN}" init "${init_args[@]}"
fi

cat <<EOF

Meguri is ready.

Open Codex or Claude Code in the target project, invoke /meguri, and ask:
  Initialize this project with Meguri.

If slash entrypoints need selection:
  Claude Code: type /, search meguri, choose /meguri
  Codex: restart/open a new session, type /, search meguri, choose prompts:meguri
  Codex alternatives: /skills -> meguri, or \$meguri init

If a newly installed entrypoint does not appear, restart Codex / Claude Code
or open a new session in this project.

After updating an existing project, run meguri refresh again from the target
project to refresh Meguri entrypoints from the official repository, then run
meguri init to repair or initialize the project pack. If network access is
unavailable, run meguri refresh --offline to use the bundled templates.

If a later Meguri step is not found, refresh the executable path with:
  python3 -m pipx ensurepath
EOF
