#!/usr/bin/env bash
set -euo pipefail

install_skill_claude_code() {
  local src="$1"
  local name="$2"
  local mode="$3"
  local dest="${HOME}/.claude/skills/${name}"
  install_bundle "$src" "$dest" "$mode"
}
