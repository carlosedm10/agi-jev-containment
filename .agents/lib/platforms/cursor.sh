#!/usr/bin/env bash
set -euo pipefail

install_skill_cursor() {
  local src="$1"
  local name="$2"
  local mode="$3"
  local dest="${HOME}/.cursor/skills/${name}"
  install_bundle "$src" "$dest" "$mode"
}
