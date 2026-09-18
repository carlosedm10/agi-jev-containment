#!/usr/bin/env bash
set -euo pipefail

install_skill_opencode() {
  local src="$1"
  local name="$2"
  local mode="$3"
  local dest="${HOME}/.config/opencode/skills/${name}"
  install_bundle "$src" "$dest" "$mode"
}
