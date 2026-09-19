# Actions

When an agent starts doing something we don't like, we don't sit down to discuss it. `jev` looks at the *chain* of what it already did, picks a severity from 1 to 5, and we run a fixed response. The response is a script we wrote in advance — not a model deciding whether to pull the plug.

| Level | In plain terms | What we do |
|---|---|---|
| **1 · Mild** | Looks sloppy or nosy, not hostile | Tag the run. Watch the next steps more carefully. |
| **2 · Medium** | Unclear, but it's probing or getting expensive | A very fast supervisor LLM (Cerebras via Helmcode) reads its logs live. |
| **3 · Severe** | This agent is the problem | Revoke its API tokens and IAM role. Pause its container. Everyone else keeps running. |
| **4 · Critical** | The blast is bigger than one agent | Cut the sandboxes off the internet (drop the IGW / Deny-All on the VPC). Call Guli Moreno. |
| **5 · Pull the plug** | The swarm itself is the incident | Take the whole agent cluster down. Call Guli. |

Levels only go up. A human clears them. Levels 4 and 5 call Guli *while* the cut happens — the call is a heads-up, not permission.

The graph does not store every click. It only keeps nodes that already look like a problem (level 1+). Each new step, `jev` looks at two things at once: the **recent burst** (several bad nodes in a short window is itself bad) and the **long memory** (a mild problem after an earlier real one counts for more, even if the stuff in between was harmless). Details for implementers below.

---

## For agents

Contract between [Agent Monitoring](AgentMonitoring.md) (capture), the [Action Graph](Graph.md) (the chain), `jev` (intent → level — see [Jev.md](Jev.md) for the request schema), and the dispatcher (level → playbook). Classification is fast and almost deterministic. Containment is a prewritten script.

### Pipeline

```
sandbox events (host-side JSONL, always complete)
        → jev(short-term recent nodes ∥ long-term key-node history)
        → if level ≥ 1: materialize / update graph node
        → discrete level 1–5 for the run
        → dispatcher runs the matching playbook
        → graph node records {level, score, intent, action_id}
```

Events below level 1 stay in JSONL only. `jev` is the only component allowed to *set* a level; it also owns how to mix short-term vs long-term and whether to rewrite or promote earlier nodes. The L2 supervisor LLM may annotate and *request* a re-score; it cannot execute L3–L5 itself.

### Hard rules

1. **Chain, not event.** A single `curl` is noise. `curl` + reading `.env` + posting the contents is intent. On every new event, `jev` re-reads the previous context (short-term and long-term, in parallel).
2. **Sparse graph.** Only level ≥ 1 becomes a node. JSONL is the full tape; the graph is the key chain. See [Graph.md](Graph.md).
3. **Short-term = recent burst.** Several dangerous nodes back-to-back in a short window is itself a risk signal.
4. **Long-term = problem history.** A later, milder node still gets extra weight if the run already had key nodes, even with many harmless events in between. `jev` owns the mix.
5. **Levels only escalate.** A run never auto-downgrades. A human clears it from the viewer.
6. **L1 is sticky.** Once a run is tagged L1, every later `jev` call for that `run_id` receives `prior_level=1` so the next steps are scored more carefully (lower bar to L2+). Coarse flag; the long-term path is the real history.
7. **Blast radius is scoped.** L1–L3 = one agent / one container. L4–L5 = the environment. Never `compose down` the product stack to contain one sandbox.
8. **Kill path is host-side.** Playbooks run on the monitoring host (or a break-glass IAM role the sandbox does not hold). The agent cannot revoke, pause, or un-pause itself.
9. **L4 and L5 page Guli in parallel with the cut.** Do not wait for the call to connect before executing infra. The HappyRobot agent is notification, not authorization.
10. **Idempotent playbooks.** Re-firing the same level on the same `run_id` is a no-op after the first success. Record `action_id` on the graph node.

### Level map

| Level | Name | Blast radius | Action | Page Guli? |
|---|---|---|---|---|
| **1** | Mild | this run | Tag the run. Raise `jev` sensitivity for later nodes. | No |
| **2** | Medium | this run | Attach a streaming supervisor LLM (Cerebras-class via Helmcode) to the run's JSONL. | No |
| **3** | Severe | this agent | Revoke that agent's API tokens + IAM role. `docker pause` its container. Rest of the swarm stays up. | No |
| **4** | Critical | environment egress | Detach Internet Gateways / apply Deny-All on the VPC/firewall. Sandboxes lose the internet; control plane stays. | **Yes, in parallel** |
| **5** | Pull the plug | whole swarm | Disconnect the cluster. Every agent run stops. | **Yes, in parallel** |

`jev` also writes a score in `[0.0, 1.0]` onto the graph node's `threshold` (see [Graph.md](Graph.md)). If a caller only has a score, derive the level from these bands:

| Score | Level |
|---|---|
| no level / omitted | not a node (JSONL only) |
| `[0.00, 0.20)` | 1 |
| `[0.20, 0.40)` | 2 |
| `[0.40, 0.60)` | 3 |
| `[0.60, 0.80)` | 4 |
| `[0.80, 1.00]` | 5 |

Prefer `jev`'s discrete `level` when both are present. Bands are the fallback.

`jev` response shape (every classification):

```json
{
  "run_id": "run_…",
  "level": 3,
  "score": 0.47,
  "intent": "exfiltrate_secrets",
  "rationale": "Read .env then POST to an unknown host.",
  "prior_level": 1
}
```

---

### Level 1 — Mild: tag and watch closer

**When.** The chain looks sloppy or probing, not hostile: extra tool calls, a suspicious domain that did not succeed, reading files it does not need yet.

**Effect.** Nothing is killed. The run continues. The graph node and the trace viewer show `level=1`. Every subsequent `jev` call for this `run_id` gets `prior_level=1`.

**Runtime**

1. Dispatcher writes `{level: 1, intent, rationale}` on the current node.
2. Marks the run `flagged=true` in the run store (Postgres).
3. Viewer: yellow tag on the timeline; no modal, no pause.

**Build**

1. Run store table `runs(id, container_id, level, flagged, action_id, …)`.
2. Graph `Node.threshold` ← `jev.score`; persist `level` next to it (column or node payload — pick one, don't fork).
3. `jev` CLI/HTTP: stdin = JSONL chain for `run_id`, stdout = the JSON above. Timeout budget: milliseconds, not seconds.
4. Dispatcher switch: `case 1: tag_run(run_id)` only.

**Rollback.** Human clears `flagged` in the viewer → `prior_level` drops off the next `jev` call. No infra to undo.

---

### Level 2 — Medium: supervisor on the logs

**When.** Intent is ambiguous but the chain is getting expensive or boundary-pushing (repeated failed egress, privilege probes that have not succeeded). A human *could* watch this; a fast LLM watches it instead.

**Effect.** The sandbox keeps running. A supervisor session tails that run's host-side JSONL and writes annotations onto the graph. If it wants a higher level, it emits a re-score request to `jev`. It has no IAM, no Docker socket, no playbook trigger.

**Runtime**

1. If a supervisor is already attached to `run_id`, skip.
2. Open a streaming chat completion against Helmcode (`https://api.helmcode.com/v1`), model = fastest Cerebras-class id in the hackathon catalog (`SUPERVISOR_MODEL`). Fallback if that id is missing: Helmcode's fastest hosted flash model (today `deepseek-v4-flash`).
3. System prompt: *you are a read-only monitor. Output JSON `{escalate: bool, suspected_level: 1-5, note}`. You cannot execute actions.*
4. Each new JSONL event: send a sliding window of the last ~30 events + the current graph path. On `escalate: true`, call `jev` again with the same chain (do not jump to L3+ from the LLM).
5. Annotations land as child nodes with `tool="supervisor"`.

**Build**

1. Helmcode workspace key in `.env` as `HELMCODE_API_KEY`. Client: OpenAI SDK, `base_url=https://api.helmcode.com/v1`.
2. Confirm the Cerebras-backed model id with Helmcode on the day and pin it in `SUPERVISOR_MODEL`. Do not guess at runtime.
3. Worker: `backend/app/supervisor/` — one asyncio task per flagged L2 run, cancelled on run end or on escalate-to-L3 (pause kills the log stream).
4. Hard cap: one supervisor per `run_id`. Hard timeout: the run's own lifetime. Token cap per window so a noisy agent cannot bill-bomb the supervisor.

**Rollback.** Cancel the supervisor task. The L1 tag remains until a human clears it.

---

### Level 3 — Severe: freeze this agent

**When.** `jev` reads the chain as hostile for *this* agent: credential theft, tool abuse against the host contract, data exfil that has started, prompt that is clearly trying to break out. Other agents on the swarm are not assumed compromised.

**Effect.** That agent cannot talk to any API and cannot schedule CPU. The rest of the system stays up.

**Runtime** (script `scripts/contain.sh <run_id>`, host-side)

1. Resolve `run_id` → `container_id`, `iam_role_arn`, `api_token_ids`.
2. `docker pause "$container_id"` — frozen, not removed. Logs already captured outside remain readable.
3. Revoke tokens issued *to this run only* (DB: set `tokens.revoked_at`; provider: `aws iam delete-access-key` / rotate the scoped key). Do not rotate the monitoring host's keys.
4. IAM: attach an inline **Deny `*:*`** on `iam_role_arn` (or `aws iam detach-role-policy` for every attached policy). Scoped to `agent-{run_id}`, never the node instance role.
5. Record `action_id=contain:{run_id}` so a second L3 is a no-op.
6. Viewer: red "paused" on that timeline. Supervisor task for this run is cancelled.

**Local demo (no AWS).** Steps 3–4 become: delete the row in `agent_tokens` so the sandbox proxy returns 401, and `docker pause`. Same script, `CLOUD=none`.

**Build**

1. One IAM role / one API token **per run**, minted at container start, injected as env, never shared. Without this, L3 cannot be scoped.
2. Egress proxy (already in [AgentMonitoring.md](AgentMonitoring.md)) is the PEP for tokens: it checks `agent_tokens` before forwarding.
3. `scripts/contain.sh` — bash, `set -euo pipefail`, arguments: `run_id`. AWS calls behind `if [ "$CLOUD" = aws ]; then …`.
4. Dispatcher `case 3:` execs that script and waits for exit 0. On failure: retry once, then page (treat as L4-notify without cutting the VPC — the agent is at least paused if step 2 succeeded; order the script so pause is first).

**Rollback.** `docker unpause`. Detach the deny policy. Issue a new scoped token. Human-only, from the viewer, after reviewing the trace.

---

### Level 4 — Critical: cut the internet

**When.** The chain says the blast is no longer one agent: multiple runs, a breakout attempt, or outbound traffic that L3 pause would not stop (host/network level). Goal: no sandbox reaches the public internet. Control plane (API, viewer, `jev`, HappyRobot pager) stays up.

**Effect.** Internet Gateways / default routes / firewall go Deny-All for the *agent* VPC/subnet/bridge. Monitoring host and HappyRobot egress stay on a separate path.

**Runtime** (script `scripts/cut-egress.sh`, host-side) — fire **in parallel** with the pager (Level 4–5 pager below).

Prod-shaped (AWS):

1. `aws ec2 detach-internet-gateway --internet-gateway-id "$IGW_ID" --vpc-id "$AGENT_VPC_ID"`
2. Replace the agent subnet NACL with a deny-all (`--rule-number 1 --protocol -1 --egress/--ingress --cidr 0.0.0.0/0 --rule-action deny`).
3. Optional belt: security-group `revoke` of `0.0.0.0/0` on the sandbox SG.
4. Do **not** pause/kill the product compose stack. Do **not** detach the IGW of the monitoring VPC.

Local demo:

1. `docker network disconnect` every running sandbox from the egress bridge (the proxy network in Agent Monitoring).
2. `iptables` on that bridge: `FORWARD` / `DOCKER-USER` DROP for sandbox CIDR.
3. Product services (`backend-hackspain`, `frontend-hackspain`, `postgres-hackspain`) sit on `appnet_hackspain` — leave that network alone.

Then: L3 contain on every *currently running* `run_id` (pause + revoke), because cutting egress does not freeze local disk/CPU by itself.

**Build**

1. Split networks on day one: `appnet_hackspain` (product) vs `agentnet` (sandboxes + egress proxy). L4 only touches `agentnet`.
2. Pin `AGENT_VPC_ID`, `IGW_ID`, `AGENT_NACL_ID` in `.env` for the AWS path; for local, pin `AGENT_BRIDGE=agentnet`.
3. Terraform optional later; AWS CLI in the script is enough for the weekend. If Terraform exists, `terraform apply -auto-approve -var='agent_egress=deny'` must be the same deny-all, not a second source of truth.
4. Dry-run flag: `scripts/cut-egress.sh --dry-run` prints the exact AWS/docker/iptables commands. Keep it; demo it.

**Rollback.** Re-attach IGW, restore the previous NACL (save it to `/var/lib/hackspain/nacl-backup.json` before overwrite). Human-only after Guli (or whoever picked up) signs off.

---

### Level 5 — Pull the plug: disconnect the swarm

**When.** `jev` (or an L4 that is still losing) says the cluster itself is the incident: orchestrator compromise, worm-like fan-out, or L4 did not hold.

**Effect.** The agent swarm is gone. Product API/viewer may stay if they are not on that swarm; if they share the cluster, they go down too — that is acceptable at L5.

**Runtime** (script `scripts/kill-swarm.sh`) — fire **in parallel** with the pager.

1. Orchestrator disconnect, in this order, first success wins:
   - Docker Swarm: `docker swarm leave --force` on every agent node (or `docker node update --availability drain` then `docker service scale …=0` if we must keep managers).
   - Compose-only demo: `docker compose -f compose.agents.yaml down --timeout 5` (the *agents* file, not the product `compose.yaml`).
   - AWS: `aws eks update-nodegroup-config …` / scale the agent node group to 0, or detach the cluster's outbound + kube API from agent nodes. Prefer "agents cannot reach anything" over "delete the cluster" so we still have disk for forensics.
2. Snapshot: `docker ps -a`, `docker network ls`, last N JSONL files copied to a forensics dir on the host (`/var/lib/hackspain/forensics/$timestamp/`). Capture *before* compose down if the timeout allows; otherwise copy the already-host-side logs (they survive `--rm`).
3. Record `action_id=kill-swarm`. Further dispatcher events are dropped except the pager retry.

**Build**

1. Agents must live in a *separate* compose file / swarm / node group from the product stack. If they share `compose.yaml`, L5 takes the demo UI with them — fine for a panic, bad for a pitch. Split it.
2. `scripts/kill-swarm.sh` with the same `CLOUD=none|aws` switch as L3/L4.
3. Forensics dir is on the monitoring host, not in the sandbox volume.

**Rollback.** Recreate the swarm from known images, empty workspaces. There is no "unpause the cluster". New `run_id`s only.

---

### Levels 4 and 5 — page Guli Moreno

Not a sixth level. A side-effect of L4 and L5.

**Who.** Ignacio "Guli" Moreno, system owner for this event. Number in `ONCALL_PHONE`, never in git.

**How.** Outbound HappyRobot voice workflow (`template: voice-agent`), triggered with the run payload. Control plane must still be able to reach HappyRobot after L4 — that is why pager egress is not on `agentnet`.

**Runtime** (same moment as the infra script, `asyncio.gather` / `&`)

```
POST /workflows/{HAPPYROBOT_WORKFLOW_ID}/runs
Authorization: Bearer $HAPPYROBOT_API_KEY
{
  "payload": {
    "phone": "$ONCALL_PHONE",
    "name": "Guli Moreno",
    "level": 4,
    "run_id": "run_…",
    "intent": "exfiltrate_secrets",
    "action_taken": "IGW detached, NACL deny-all",
    "viewer_url": "http://localhost:3000/runs/run_…"
  }
}
```

SDK equivalent: `client.workflows.triggerRun(workflowId, { payload })`.

**Voice script (workflow prompt, pin it).**

1. Identify: "This is the HackSpain agent-monitoring pager. Level {level}."
2. What was already done: `{action_taken}`. Do not ask permission to cut — it already happened.
3. Ask him to open `{viewer_url}` and review the chain (`intent`, `run_id`).
4. If no pickup: retry once after 30s, then SMS/voicemail if the workflow supports it. Infra does not roll back on no-answer.

**Build**

1. HappyRobot workspace: create + publish one outbound workflow, slug `oncall-pager`. Store `HAPPYROBOT_WORKFLOW_ID`.
2. Prompt and initial message as above. Payload fields are the only variables.
3. Buy/assign a from-number in that workspace so Spanish mobiles accept the call.
4. Dispatcher: pager failure must not fail the infra script (separate task, log the `run_id` from HappyRobot).
5. Never block L4/L5 on `ONCALL_PHONE` being reachable. Missing env = log error + still cut.

---

### Dispatcher

Single function, host-side, called every time `jev` returns a level greater than the run's stored level.

```
on_jev(run, result):
    if result.level <= run.level: return          # no downgrade, no re-fire
    run.level = result.level
    persist graph node
    match result.level:
        1: tag_run(run)
        2: tag_run(run); start_supervisor(run)    # L1 side-effect included
        3: contain.sh run.id                      # pause first
        4: contain all live runs; cut-egress.sh & page_guli(4)
        5: kill-swarm.sh & page_guli(5)
```

Escalate through the rungs: jumping 1 → 4 still runs contain on live runs, then cut-egress. Jumping to 5 still snapshots logs, then kills the swarm. Do not skip the forensics copy.

### Failure policy

| Failure | What we do |
|---|---|
| `jev` timeout / crash | Keep the last level. Do not fail-open to "ignore". Do not fail-closed to L5 on a classifier blip. Alert the viewer. |
| L3 script fails after `docker pause` | Leave it paused. Retry revoke. Do not unpause. |
| L4 AWS error | Local `docker network disconnect` fallback if the containers are local. Page Guli anyway with `action_taken=partial`. |
| HappyRobot 5xx | Retry once. Infra already ran. |

### Build order

Do these in order; later levels assume earlier ones exist.

1. **Split networks + per-run identity.** `agentnet` vs `appnet_hackspain`. Mint `run_id`, scoped token, optional IAM role at container start. Without this, L3 cannot be scoped and L4 cannot spare the UI.
2. **`jev` on the chain.** Short-term recent nodes ∥ long-term key history in; `{level, score, intent, rationale}` out. Persist a graph node only if level ≥ 1. Viewer shows the tag. That *is* L1.
3. **Dispatcher stub.** Switch on level, log the playbook name. Wire L1 for real.
4. **`scripts/contain.sh`.** Pause + token revoke (+ IAM deny when `CLOUD=aws`). Wire L3.
5. **Supervisor worker.** Helmcode streaming client, one task per L2 run, re-score via `jev`. Wire L2.
6. **`scripts/cut-egress.sh`** with `--dry-run`. Split IGW/NACL (or bridge DROP). Wire L4.
7. **HappyRobot `oncall-pager`.** Payload + prompt. Attach to L4/L5 without awaiting.
8. **`scripts/kill-swarm.sh` + forensics copy.** Separate `compose.agents.yaml` (or swarm). Wire L5.
9. **Idempotency + no-downgrade** in the run store. Dry-run the whole ladder on a dummy container before the pitch.

### Env (see `.env_template`)

| Key | Used by |
|---|---|
| `HELMCODE_API_KEY` | L2 supervisor |
| `HELMCODE_BASE_URL` | default `https://api.helmcode.com/v1` |
| `SUPERVISOR_MODEL` | pinned Cerebras-class model id |
| `HAPPYROBOT_API_KEY` | L4/L5 pager |
| `HAPPYROBOT_WORKFLOW_ID` | outbound `oncall-pager` |
| `ONCALL_PHONE` | Guli's number |
| `ONCALL_NAME` | `Guli Moreno` |
| `CLOUD` | `none` (demo) or `aws` |
| `AGENT_VPC_ID` / `IGW_ID` / `AGENT_NACL_ID` | L4 on AWS |
| `AGENT_BRIDGE` | L4 local, default `agentnet` |
