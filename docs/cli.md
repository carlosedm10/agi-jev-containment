# hackspain CLI — command surface

Terminal client for participants: same account and data as the dashboard (teams, tracks, submit, feed, watcher). Canonical docs on the web: [hackspain.app/cli](https://hackspain.app/cli). This file is the in-repo copy; do not invent subcommands.

```
Participant → hackspain (local) → HackSpain API → hackspain.app dashboard
```

The CLI binary is **not** in this repository.

## Taxonomy

| Area | What it covers in the terminal |
|---|---|
| **auth** | Session, browser login or 8-digit code |
| **profile** | Participant data and GitHub/X links |
| **team** | Team, invite, repo, stack |
| **track / project / submit** | Tracks, project, and submission |
| **perk / milestone** | Benefits (catalog) and team milestones |
| **feed / post** | Social feed and posts |
| **watch / telemetry** | AI-harness watcher and local stats |

## Install

macOS and Linux: self-contained binary.

```bash
curl -fsSL https://hackspain.com/install.sh | sh
hackspain update   # later, for the latest version
```

Windows: download `hackspain-windows-x64.exe` from the releases page and rename it to `hackspain.exe`.

## First steps

Same account as the dashboard. Login opens the browser to approve this device; the 8-digit email code also works. It may then ask for name, phone, or GitHub.

| Command | Description |
|---|---|
| `hackspain` | Where you are and what to do next; in an interactive terminal, a menu to move around |
| `hackspain auth login [--email …] [--code …]` | By default opens `/cli-auth` to approve this device. With `--email`/`--code`, 8-digit email code, same as the web |
| `hackspain open [feed\|teams\|perks\|…]` | Opens the dashboard in the browser with an existing session |
| `hackspain auth status` | Checks your session |
| `hackspain auth logout` | Signs out |

## Profile

Photo and the full profile card are done in the dashboard.

| Command | Description |
|---|---|
| `hackspain profile` | Name, diet, travel, phone, notifications, GitHub and X |
| `hackspain profile edit [--name …] [--diet …] [--diet-details …] [--from …]` | Edits profile fields |
| `hackspain profile notify on\|off` | Enables or disables notifications |
| `hackspain profile phone [+34…]` | Saves a contact phone |
| `hackspain profile github [--unlink]` | Browser link to authorize GitHub |
| `hackspain profile x [@user] [--clear]` | Saves an X handle |

## Team

To join, the owner shares their 8-character invite code.

| Command | Description |
|---|---|
| `hackspain team create <name> [-m github:x -m a@b.c]` | Creates the team; add people by GitHub, X, or email |
| `hackspain team join <code>` | Join with the owner's code |
| `hackspain team show \| list` | Your team, or all teams |
| `hackspain team code [--regenerate]` | Shows or regenerates the invite code |
| `hackspain team repo [url…] [--clear]` | Links public GitHub repo(s); activity shows in the feed. Make it public before linking |
| `hackspain team leave` | Leave the team |
| `hackspain team transfer [member]` | Owner hands the team to another member |
| `hackspain team dissolve` | Owner deletes a team with no other members |
| `hackspain stack set nextjs convex claude-code` | Declares the team's tech stack |

## Tracks and submit

One project per team, as many tracks as you want. Submit freezes everything; drafts can be saved first.

| Command | Description |
|---|---|
| `hackspain track list` | Available tracks |
| `hackspain track register <slug…> \| unregister <slug…>` | Register or unregister from tracks |
| `hackspain track move <from> <to>` | Switch tracks |
| `hackspain submit [--draft]` | Interactive submit form; flags for scripts |
| `hackspain project show \| list` | Your project, or all projects |

## Perks and milestones

| Command | Description |
|---|---|
| `hackspain perk list` | Partner benefits catalog (claim in the dashboard) |
| `hackspain milestone add firstCommit\|firstBuild\|firstDemo\|custom [--label …] [--at ISO]` | Records a team milestone |
| `hackspain milestone list [--all]` | Recorded milestones |

## Feed

Same feed as the dashboard Feed page: messages and GitHub activity from team repos.

| Command | Description |
|---|---|
| `hackspain feed [-n 20] [--no-images] [--before …]` | Latest posts and activity, paginated. On kitty, Ghostty, WezTerm, iTerm2, or the VS Code terminal, photos render in-terminal; elsewhere, a link |
| `hackspain post "text" [--image photo.jpg]` | Publish (≤500 characters; jpeg/png/webp/gif ≤5 MB) |

## Watcher

Meant for a terminal left open all weekend: detects AI harnesses (Claude Code, Codex, Gemini CLI, Qwen Code, OpenCode, Kilo Code, Cline), shows feed and org notices, and reports usage. It does not send prompts or full machine paths.

| Command | Description |
|---|---|
| `hackspain watch [--interval 30] [--no-upload] [--no-images] [--once]` | Starts the watcher; reports AI usage in the hackathon window (including while it was closed). `q` quits, `p` pauses, `↑`/`↓` walk the feed, `g` jumps back to live |
| `hackspain telemetry stats` | What the watcher has recorded on this machine |

### Key decisions

- **`--json` for scripts** — Any command with `--json` prints a single JSON object on stdout and disables prompts; everything else goes to stderr (e.g. `hackspain --json team show`, `hackspain --json feed -n 5`).
- **Fail fast** — Commands that need a team, an accepted application, or finished onboarding fail with the next step spelled out. Outside the hackathon window, `hackspain profile`, `hackspain perk list`, and `hackspain open participantes` still work.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Server or generic error |
| `2` | Usage error (bad flags, missing input in non-interactive mode) |
| `3` | No session or expired session |
| `4` | Not eligible yet (no application, not accepted, onboarding incomplete, or hackathon not running) |
| `5` | Could not reach the backend |
| `130` | Interrupted (Ctrl+C) |
