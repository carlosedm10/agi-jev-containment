## Agent Monitoring

Each agent runs inside an isolated environment (sandbox — one Docker container per run). We need full visibility into what the agent does in there: which actions it takes, which tools it executes, its reasoning, and the trace that connects them. Logs are captured **outside** the container (stdout, filesystem diff, network egress), so the agent cannot tamper with or hide its own trail.

### What we capture

| Signal | Source | How |
| --- | --- | --- |
| Agent transcript | The agent harness itself | `stream-json` / JSONL output — every message, tool call, tool result, and reasoning step |
| Actions / commands | Every process the agent spawns | stdout/stderr captured by the container runtime |
| File changes | Workspace state | `git diff` (or `docker diff`) on the workspace before/after the run |
| Network | Outbound requests | Egress routed through a proxy on the container's bridge network |
| Resources | CPU / memory / processes | `docker stats` / `docker events` |

### Requirements

- **Log everything** as structured events (JSONL), timestamped and ordered — one event per action/tool call.
- **Per-run isolation**: each run gets its own log directory and a clean container (`--rm`), no state leaking between runs.
- **Tamper-proof**: capture happens on the host side; nothing inside the sandbox can modify the record.
- **Queryable**: logs feed a trace viewer / timeline so we can replay a run end to end.

### Classification

Every captured action is passed through `jev`, our classifier, which labels each event (e.g. tool execution, file edit, network request, reasoning step) so runs can be filtered, compared, and scored.
