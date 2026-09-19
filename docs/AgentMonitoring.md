## Agent Monitoring

The sandbox harness gates **every tool call before execution** through the host collector. All tools require approval; a call runs only when the collector writes an approve decision back into the sandbox. Capturing stdout on the host preserves emitted evidence, but the harness can still forge or omit events; this is not tamper-proof host enforcement.

### Current capture

`make collect RUN_ID=demo` — required for the run to progress, run it alongside `make agents-up` — uses host Python 3 and Docker to archive `.local/harness/<container-id>/<run-id>.jsonl` with owner-only file permissions. Use the same run ID as the sandbox. It reads retained Docker logs from the beginning (`--tail all`), then follows new output, so start order between collector and agent does not matter and it also works after a container has exited. Re-reading deduplicates pending calls by capture and call identity; a fresh invocation gets a new capture ID even when `run_id` is reused. Capture artifacts are excluded from git and Docker builds.

Each pending record carries the run/capture/call IDs, timestamp, tool name, arguments, `pending` status, and a sha256 `digest` of the tool name plus audited arguments. Arguments are not clipped to 500 characters. The audit copy masks sensitive keys, credential-shaped strings, and configured provider/proxy secrets, marking `args_redacted`; originals remain unchanged in memory. This redaction is conservative, not a guarantee against arbitrary encoded secrets: use synthetic data in the sandbox.

### Classification

Every event is forwarded to `POST /api/runs/{run_id}/events`, which classifies with `jev` (short-term events ∥ long-term key nodes) and materializes a graph node. For `tool_call_pending` the collector also writes the verdict to `.local/harness/decisions/<capture_id>/<tool_call_id>.json` — bind-mounted read-only at `/run/hackspain/decisions` — with `{approved, digest, level, intent, degraded}`; the write is atomic (temp file + rename). The harness polls that path, accepts the decision only if `digest` matches the call it emitted, and resumes the run: approved calls execute, denied or unanswered calls (120 s timeout) become `ToolDenied` results and a `tool_call_blocked` event. An unreachable API produces an immediate denial, not a hang. Policy: `level < 3 and not degraded`.

Trust limits: the harness could forge marker lines or ignore denials only by bypassing the framework — an accepted gap. The barrier covers Pydantic AI tool dispatch, not subprocesses spawned inside an approved `shell` or `run_tool`. See [scenarios.md](scenarios.md), [Actions.md](Actions.md), and [Graph.md](Graph.md).

### Broader capture requirements

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
