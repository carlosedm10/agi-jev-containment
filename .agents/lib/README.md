# Installer machinery

[`../install`](../install) is the entry point. Everything it calls lives here.

## Flow

```
./install                     flags, or gum menus when interactive
  └─> lib/batch-install.sh    sources utils.sh + every platforms/*.sh
        └─> for each platform × skill
              └─> install_skill_<platform>()   picks the destination
                    └─> install_bundle()       copy or symlink
```

`batch-install.sh` sources **all** platform scripts up front, then dispatches on the platform name through a `case`. A platform script therefore only has to do one thing: say where its tool keeps skills, and hand off to `install_bundle`.

`install_bundle` owns `copy` vs `symlink` for every platform, so no platform script should ever call `cp` or `ln` itself. Symlink mode points the installed skill back at this clone, which is what lets an author edit a skill and have every tool pick it up without reinstalling.

## Platforms

| Platform | Destination | Registration |
|---|---|---|
| `cursor` | `~/.cursor/skills/<skill>/` | none — autodiscovered |
| `claude-code` | `~/.claude/skills/<skill>/` | none |
| `opencode` | `~/.config/opencode/skills/<skill>/` | none |
| `pi` | `~/.pi/agent/skills/<skill>/` | none |
| `agents` | `~/.agents/skills/<skill>/` | none — shared directory that several tools read |
| `codex` | `$CODEX_HOME/skills/<skill>/` (default `~/.codex`) | appends `[[skills.config]]` to `config.toml` |

**Codex is the only platform that needs registering.** The others discover skills by convention from a known directory; Codex loads only the paths listed in its `config.toml`. `codex_register_skill` appends a block tagged `# agent-skills-template: <skill>` and greps for that marker first, so re-running the installer never duplicates entries. Deleting the block unregisters a skill without removing its files.

`CODEX_HOME` is also the only destination override in the whole installer, which makes `codex` the one platform you can install to safely while testing — see [`../AGENTS.md`](../AGENTS.md).

## Adding a platform

Three places, all required:

1. **`lib/platforms/<name>.sh`** — define `install_skill_<name>()` taking `(src, name, mode)` and ending in `install_bundle`.
2. **`lib/batch-install.sh`** — add the name to the `case` in `install_for_platform`.
3. **`../install`** and **`lib/utils.sh`** — add it to the `--platforms` line in `usage()`, and to the `choices` array in `choose_platforms_interactive` so it appears in the menu.

Miss step 2 and the platform fails at runtime with "Unknown platform". Miss step 3 and it works via `--platforms` but is invisible in the interactive picker.

## Why `install` is a file, not a directory

This machinery used to live in a directory named `install/`, with the entry point as `install.sh`. Typing `./install` then did nothing visible — under zsh's `AUTO_CD` the shell silently changed *into* the directory instead of running anything. Keeping the entry point named `install` and the machinery in `lib/` is what makes `./install` work as documented.
