#!/usr/bin/env bash
set -euo pipefail

install_skill_agents() {
  local src="$1"
  local name="$2"
  local mode="$3"
  local dest="${HOME}/.agents/skills/${name}"
  install_bundle "$src" "$dest" "$mode"
}
