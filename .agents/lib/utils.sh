#!/usr/bin/env bash
# Shared helpers for platform installers.

set -euo pipefail

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Colour only when stdout is a terminal, so piped and CI output stays clean.
if [[ -t 1 ]]; then
  C_RED=$'\033[0;31m'
  C_GREEN=$'\033[0;32m'
  C_YELLOW=$'\033[0;33m'
  C_BLUE=$'\033[0;34m'
  C_DIM=$'\033[2m'
  C_OFF=$'\033[0m'
else
  C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_DIM=""; C_OFF=""
fi

info()    { printf '%s::%s %s\n' "$C_BLUE" "$C_OFF" "$*"; }
success() { printf '%s::%s %s\n' "$C_GREEN" "$C_OFF" "$*"; }
warn()    { printf '%s::%s %s\n' "$C_YELLOW" "$C_OFF" "$*" >&2; }
error()   { printf '%s::%s %s\n' "$C_RED" "$C_OFF" "$*" >&2; }
debug()   { printf '%s..%s %s\n' "$C_DIM" "$C_OFF" "$*"; }

# Yes/no prompt — gum when available, plain read otherwise.
gum_confirm() {
  local msg="$1"
  if command -v gum >/dev/null 2>&1; then
    gum confirm "$msg"
  else
    printf '%s [y/N] ' "$msg" >&2
    local ans
    read -r ans || true
    [[ "${ans:-}" =~ ^[Yy]$ ]]
  fi
}

install_bundle() {
  local src="$1"
  local dest="$2"
  local mode="$3"
  if [[ ! -d "$src" ]]; then
    printf 'Source directory not found: %s\n' "$src" >&2
    return 1
  fi
  mkdir -p "$(dirname "$dest")"
  rm -rf "$dest"
  if [[ "$mode" == "symlink" ]]; then
    local abs
    abs="$(cd "$src" && pwd)"
    ln -sfn "$abs" "$dest"
  elif [[ "$mode" == "copy" ]]; then
    mkdir -p "$dest"
    cp -a "${src}/." "$dest/"
  else
    printf 'Invalid mode %s (expected copy or symlink)\n' "$mode" >&2
    return 1
  fi
}

skill_dir_valid() {
  [[ -f "$1/SKILL.md" ]]
}

list_skill_names() {
  local root="$1"
  local d name
  shopt -s nullglob
  for d in "${root}"/*/; do
    [[ -d "$d" ]] || continue
    name="$(basename "$d")"
    skill_dir_valid "${d%/}" || continue
    printf '%s\n' "$name"
  done | sort -u
}

escape_toml_double() {
  local s=$1
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  printf '%s' "$s"
}

# Parse first semver from `gum version` output (e.g. "gum version v0.14.5").
gum_semver() {
  gum --version 2>/dev/null | head -n1 | sed -nE 's/.*v?([0-9]+\.[0-9]+\.[0-9]+).*/\1/p'
}

# True if $1 >= $2 (semver x.y.z only).
semver_ge() {
  local a="$1" b="$2"
  [[ -n "$a" && -n "$b" ]] || return 1
  [[ "$(printf '%s\n' "$b" "$a" | sort -V | tail -n1)" == "$a" ]]
}

ensure_gum() {
  if command -v gum >/dev/null 2>&1; then
    local gv
    gv="$(gum_semver)"
    if ! semver_ge "${gv}" "0.4.0"; then
      printf '%s\n' "gum is too old (${gv:-unknown}); need >= 0.4.0 for --no-limit multi-select. Upgrade: brew upgrade gum" >&2
      return 1
    fi
    return 0
  fi

  if [[ "${OSTYPE:-}" == darwin* ]] && command -v brew >/dev/null 2>&1; then
    printf '%s\n' "Installing gum via Homebrew..." >&2
    brew install gum >/dev/null 2>&1 || brew install gum
    command -v gum >/dev/null 2>&1 || return 1
    local gv2
    gv2="$(gum_semver)"
    if ! semver_ge "${gv2}" "0.4.0"; then
      printf '%s\n' "gum installed but version ${gv2:-unknown} is below 0.4.0; upgrade: brew upgrade gum" >&2
      return 1
    fi
    return 0
  fi

  if command -v go >/dev/null 2>&1; then
    printf '%s\n' "Installing gum via go install..." >&2
    local gopath_bin="${GOPATH:-$HOME/go}/bin"
    mkdir -p "$gopath_bin"
    GOPATH="${GOPATH:-$HOME/go}" go install github.com/charmbracelet/gum@latest
    export PATH="$gopath_bin:$PATH"
    command -v gum >/dev/null 2>&1 || return 1
    local gv3
    gv3="$(gum_semver)"
    if ! semver_ge "${gv3}" "0.4.0"; then
      printf '%s\n' "gum from go install is too old (${gv3:-unknown}); need >= 0.4.0" >&2
      return 1
    fi
    return 0
  fi

  return 1
}

gum_banner() {
  local title="$1"
  local subtitle="$2"
  local url="${3:-}"
  if command -v gum >/dev/null 2>&1; then
    local styled_title styled_sub styled_url
    styled_title="$(gum style --foreground 212 --bold "$title")"
    styled_sub="$(gum style --foreground 245 "$subtitle")"
    if [[ -n "$url" ]]; then
      styled_url="$(gum style --foreground 240 --faint "$url")"
      gum style \
        --border double --border-foreground 212 \
        --padding "1 3" --margin "1 0" \
        --width 58 \
        "${styled_title}" "${styled_sub}" "${styled_url}"
    else
      gum style \
        --border double --border-foreground 212 \
        --padding "1 3" --margin "1 0" \
        --width 58 \
        "${styled_title}" "${styled_sub}"
    fi
  else
    printf '\n━━ %s ━━\n%s\n' "$title" "$subtitle"
    [[ -n "$url" ]] && printf '%s\n' "$url"
    printf '\n'
  fi
}

_gum_choose_multi() {
  local header="$1"
  shift
  # Never redirect stderr here: when stdout is a pipe ($()), gum renders the TUI on stderr.
  gum choose --no-limit \
    --selected-prefix "[x] " \
    --unselected-prefix "[ ] " \
    --header "$header" \
    "$@"
}

_gum_choose_one() {
  local header="$1"
  shift
  gum choose --header "$header" "$@"
}

_expand_without_all() {
  local item
  for item in "$@"; do
    [[ "$item" != "All" ]] && printf '%s\n' "$item"
  done
}

_selection_includes_all() {
  printf '%s\n' "$1" | grep -Fxq "All"
}

choose_platforms_interactive() {
  local choices=(
    "All"
    "cursor"
    "claude-code"
    "codex"
    "opencode"
    "pi"
    "agents"
  )
  if command -v gum >/dev/null 2>&1; then
    local raw
    raw="$(_gum_choose_multi "Select platforms (↑/↓, space to toggle, enter — pick All for everything):" \
      "${choices[@]}")"
    if _selection_includes_all "$raw"; then
      _expand_without_all "${choices[@]}"
    else
      printf '%s\n' "$raw"
    fi
  else
    printf '%s\n' "Available platforms: ${choices[*]}" >&2
    printf 'Enter comma-separated names, \"all\", or empty for all: ' >&2
    local line
    read -r line || true
    line="$(echo "$line" | xargs)"
    local line_lc
    line_lc="$(echo "$line" | tr '[:upper:]' '[:lower:]')"
    if [[ -z "$line" || "$line_lc" == "all" ]]; then
      _expand_without_all "${choices[@]}"
      return
    fi
    IFS=',' read -ra picked <<<"$line"
    local p
    for p in "${picked[@]}"; do
      echo "$(echo "$p" | xargs)"
    done
  fi
}

choose_skills_interactive() {
  local -a names=( "$@" )
  if [[ ${#names[@]} -eq 0 ]]; then
    printf '%s\n' "No skills found under skills/ — add folders with SKILL.md." >&2
    return 1
  fi
  if command -v gum >/dev/null 2>&1; then
    local choices=( "All" )
    choices+=( "${names[@]}" )
    local raw
    raw="$(_gum_choose_multi "Select skills (↑/↓, space to toggle, enter — pick All for everything):" \
      "${choices[@]}")"
    if _selection_includes_all "$raw"; then
      printf '%s\n' "${names[@]}"
    else
      printf '%s\n' "$raw"
    fi
  else
    printf '%s\n' "Skills: ${names[*]}" >&2
    printf 'Enter comma-separated names or \"all\" (default: all): ' >&2
    local line
    read -r line || true
    line="$(echo "$line" | xargs)"
    local line_lc
    line_lc="$(echo "$line" | tr '[:upper:]' '[:lower:]')"
    if [[ -z "$line" || "$line_lc" == "all" ]]; then
      printf '%s\n' "${names[@]}"
      return
    fi
    IFS=',' read -ra picked <<<"$line"
    local p
    for p in "${picked[@]}"; do
      echo "$(echo "$p" | xargs)"
    done
  fi
}

choose_mode_interactive() {
  if command -v gum >/dev/null 2>&1; then
    _gum_choose_one "Install mode:" "symlink" "copy"
  else
    printf 'Install mode [symlink/copy] (default copy): ' >&2
    local m
    read -r m || true
    m="$(echo "$m" | xargs)"
    [[ -z "$m" ]] && m="copy"
    printf '%s\n' "$m"
  fi
}
