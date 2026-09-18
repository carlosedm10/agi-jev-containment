# hackspain CLI — The One Doc

Terminal client for participants: same account and same data as the dashboard (teams, tracks, submission, feed, and watcher). Canonical documentation on the web: [hackspain.app/cli](https://hackspain.app/cli).

```
Participant → hackspain (local) → HackSpain API → hackspain.app dashboard
```

## The taxonomy

| Area | What it covers in the terminal |
| --- | --- |
| **auth** | Session, login via browser or 8-digit code |
| **profile** | Participant details and GitHub/X links |
| **team** | Team, invitations, repo, stack |
| **track / project / submit** | Tracks, project, and submission |
| **perk / milestone** | Perks (catalog) and team milestones |
| **feed / post** | Social feed and posts |
| **watch / telemetry** | Watcher for AI harnesses and local stats |

## Getting started

| Command | Description |
| --- | --- |
| `hackspain` | Where you are and what to do next; in an interactive terminal, a menu to navigate |
| `hackspain auth login [--email …] [--code …]` | By default opens `/cli-auth` to approve this device. With `--email`/`--code`, 8-digit code by email, as on the web |
| `hackspain open [feed\|teams\|perks\|…]` | Opens the dashboard in the browser, already signed in |
| `hackspain auth status` | Checks your session |
| `hackspain auth logout` | Signs out |

## Profile

The photo and full profile are done in the dashboard.

| Command | Description |
| --- | --- |
| `hackspain profile` | Name, diet, travel, phone, notifications, GitHub, and X |
| `hackspain profile edit [--name …] [--diet …] [--diet-details …] [--from …]` | Edits profile data |
| `hackspain profile notify on\|off` | Enables or disables notifications |
| `hackspain profile phone [+34…]` | Saves contact phone number |
| `hackspain profile github [--unlink]` | Link to authorize GitHub in the browser |
| `hackspain profile x [@user] [--clear]` | Saves X handle |

## Team

To join, the owner shares their 8-character invitation code.

| Command | Description |
| --- | --- |
| `hackspain team create <name> [-m github:x -m a@b.c]` | Creates the team; adds people by GitHub, X, or email |
| `hackspain team join <code>` | Joins with the owner's code |
| `hackspain team show \| list` | Your team, or all teams |
| `hackspain team code [--regenerate]` | Shows or regenerates the invitation code |
| `hackspain team repo [url…] [--clear]` | Links public GitHub repo(s); activity shows in the feed. Make it public before linking |
| `hackspain team leave` | Leaves the team |
| `hackspain team transfer [member]` | The owner hands the team over to another member |
| `hackspain team dissolve` | The owner deletes a team with no other members |
| `hackspain stack set nextjs convex claude-code` | Declares the team's tech stack |

## Tracks and submission

One project per team, as many tracks as you want. Submitting freezes everything; drafts can be saved beforehand.

| Command | Description |
| --- | --- |
| `hackspain track list` | Available tracks |
| `hackspain track register <slug…> \| unregister <slug…>` | Join or leave tracks |
| `hackspain track move <from> <to>` | Switch tracks |
| `hackspain submit [--draft]` | Interactive submission form; flags for scripts |
| `hackspain project show \| list` | Your project, or all projects |

## Perks and milestones

| Command | Description |
| --- | --- |
| `hackspain perk list` | Partner perks catalog (claim in the dashboard) |
| `hackspain milestone add firstCommit\|firstBuild\|firstDemo\|custom [--label …] [--at ISO]` | Records a team milestone |
| `hackspain milestone list [--all]` | Recorded milestones |

## Feed

Same feed as the dashboard's Feed page: messages and GitHub activity from team repos.

| Command | Description |
| --- | --- |
| `hackspain feed [-n 20] [--no-images] [--before …]` | Latest posts and activity, paginated. In kitty, Ghostty, WezTerm, iTerm2, or the VS Code terminal, photos render in the terminal; elsewhere, a link |
| `hackspain post "text" [--image photo.jpg]` | Posts (≤500 characters; jpeg/png/webp/gif ≤5 MB) |

## Watcher

Meant for a terminal left open all weekend: detects AI harnesses (Claude Code, Codex, Gemini CLI, Qwen Code, OpenCode, Kilo Code, Cline), shows the org feed and notifications, and reports usage. It does not send prompts or full paths from your machine.

| Command | Description |
| --- | --- |
| `hackspain watch [--interval 30] [--no-upload] [--no-images] [--once]` | Starts the watcher; reports AI usage during the hackathon window (including while it was closed). `q` quits, `p` pauses, `↑`/`↓` scroll the feed, `g` returns to live |
| `hackspain telemetry stats` | What the watcher has recorded on this machine |

### Key decisions

- **`--json` in scripts** — Any command with `--json` prints a single JSON object to stdout and disables prompts; everything else goes to stderr (e.g. `hackspain --json team show`, `hackspain --json feed -n 5`).
- **Fail fast** — Commands that require a team, an accepted application, or completed onboarding fail with the next step indicated. Outside the hackathon window, `hackspain profile`, `hackspain perk list`, and `hackspain open participantes` still work.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | All good |
| `1` | Server or generic error |
| `2` | Usage error (bad flags, missing input in non-interactive mode) |
| `3` | No session or expired session |
| `4` | Not yet eligible (no application, not accepted, incomplete onboarding, or hackathon not running) |
| `5` | Could not reach the backend |
| `130` | Interrupted (Ctrl+C) |
