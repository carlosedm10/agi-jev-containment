#!/usr/bin/env bash
set -euo pipefail

codex_register_skill() {
  local dest_dir="$1"
  local name="$2"
  local codex_home="${CODEX_HOME:-${HOME}/.codex}"
  local cfg="${codex_home}/config.toml"
  mkdir -p "${codex_home}"
  [[ -f "${cfg}" ]] || touch "${cfg}"

  local marker="# agent-skills-template: ${name}"
  if grep -qF "${marker}" "${cfg}" 2>/dev/null; then
    return 0
  fi

  local abs
  abs="$(cd "${dest_dir}" && pwd)"
  local escaped
  escaped="$(escape_toml_double "${abs}")"

  {
    printf '\n%s\n' "${marker}"
    printf '%s\n' "[[skills.config]]"
    printf '%s\n' "path = \"${escaped}\""
    printf '%s\n' "enabled = true"
  } >>"${cfg}"
}

install_skill_codex() {
  local src="$1"
  local name="$2"
  local mode="$3"
  local codex_home="${CODEX_HOME:-${HOME}/.codex}"
  local dest="${codex_home}/skills/${name}"
  install_bundle "$src" "$dest" "$mode"
  codex_register_skill "$dest" "$name"
}
