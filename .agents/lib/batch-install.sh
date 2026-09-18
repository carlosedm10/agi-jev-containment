#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/utils.sh
source "${ROOT}/lib/utils.sh"
# shellcheck disable=SC1090
for f in "${ROOT}/lib/platforms"/*.sh; do
  # shellcheck source=/dev/null
  source "$f"
done

MODE="copy"
SKILLS_DIR="${ROOT}/skills"
SKILLS_LIST=""
PLATFORMS_LIST=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --skills-dir)
      SKILLS_DIR="$2"
      shift 2
      ;;
    --skills)
      SKILLS_LIST="$2"
      shift 2
      ;;
    --platforms)
      PLATFORMS_LIST="$2"
      shift 2
      ;;
    *)
      printf 'Unknown arg: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

IFS=',' read -ra PLATFORMS <<<"${PLATFORMS_LIST// /}"
IFS=',' read -ra SKILL_NAMES <<<"${SKILLS_LIST// /}"

install_for_platform() {
  local platform="$1"
  local src="$2"
  local name="$3"
  local mode="$4"
  case "$platform" in
    cursor) install_skill_cursor "$src" "$name" "$mode" ;;
    claude-code) install_skill_claude_code "$src" "$name" "$mode" ;;
    codex) install_skill_codex "$src" "$name" "$mode" ;;
    opencode) install_skill_opencode "$src" "$name" "$mode" ;;
    pi) install_skill_pi "$src" "$name" "$mode" ;;
    agents) install_skill_agents "$src" "$name" "$mode" ;;
    *)
      printf 'Unknown platform: %s\n' "$platform" >&2
      return 1
      ;;
  esac
}

for platform in "${PLATFORMS[@]}"; do
  [[ -z "$platform" ]] && continue
  for name in "${SKILL_NAMES[@]}"; do
    [[ -z "$name" ]] && continue
    src="${SKILLS_DIR}/${name}"
    if ! skill_dir_valid "$src"; then
      printf 'Skipping %s (missing SKILL.md under %s)\n' "$name" "$src" >&2
      continue
    fi
    install_for_platform "$platform" "$src" "$name" "$MODE"
    printf '[ok] %s → %s\n' "$name" "$platform"
  done
done

exit 0
