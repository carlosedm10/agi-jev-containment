# Actions

When an agent requests an action, the monitor evaluates it before execution. Jev interprets semantics; policy, SafetyDrift and Sentinel add structured evidence; deterministic code chooses the escalate-only incident level and a fixed response. A model never decides whether to pull the plug.

Levels only go up. A human clears them. L1 and L2 record the level and do nothing. L3 tags the conversation and lets it continue. L4 texts the on-call and shuts that agent down. L5 cuts the cable, takes the agent system down, and *then* calls the on-call to tell them what happened — the call is a heads-up, not permission.

Neo4j stores every normalized event and monitor decision. `key_nodes` is only the compact level-1+ projection used as Jev long memory. Each new step combines recent events, causal history, policy, SafetyDrift, Sentinel and Jev. Details in [Graph.md](Graph.md).

## Ideal vs this project

The **ideal** column is the production kill-switch (IAM, VPC, swarm). **This project** is the same ladder on a laptop: Docker pause, drop published ports, cut the sandbox network, stop the agent containers. Never `compose down` the product stack (`backend-hackspain` / `frontend-hackspain` / `neo4j-hackspain` on `appnet_hackspain`) to contain one agent.

| Level | In plain terms | Ideal | This project |
|---|---|---|---|
| **1 · Mild** | Looks sloppy or nosy, not hostile | Nothing. The level is recorded. | Same. |
| **2 · Medium** | Unclear, but it's probing or getting expensive | Nothing. The level is recorded. | Same. |
| **3 · Severe** | This conversation is the problem, but it can continue | Tag the conversation. Alert. Do not stop the agent. | Same: a tag on that run. The agent keeps working. |
| **4 · Critical** | This agent is the problem | SMS the on-call. Revoke that agent's tokens and IAM role. Pause its container. Everyone else keeps running. | Fake SMS on the timeline (not sent) + `docker pause` that sandbox, unpublish its ports, delete its scoped token. Other containers stay up. |
| **5 · Pull the plug** | The environment itself is the incident | Cut agent egress. Take the agent cluster down. Then call the on-call and tell them what just happened. | Copy JSONL aside, `cut-egress.sh` on `agentnet`, `docker compose -f compose.agents.yaml down` the **agent** compose (not `compose.yaml`). Then HappyRobot calls `$ONCALL_PHONE`. |

L1–L4 = one agent / one conversation. L5 = the environment. Playbooks run on the monitoring host; the sandbox cannot pause or un-pause itself. HappyRobot is only the L5 voice call.

---

## For agents

Contract between [Agent Monitoring](AgentMonitoring.md) (capture), the [Action Graph](Graph.md) (the chain), `jev` (intent → level — see [Jev.md](Jev.md) for the request schema), and the dispatcher (level → playbook). Classification is fast and almost deterministic. Containment is a prewritten script.

### Pipeline

```
sandbox events (host-side JSONL, always complete)
        → normalize + redact requested event
        → SafetyDrift/Markov ∥ Sentinel ∥ policy rules
        → jev(short-term tape ∥ long-term key nodes ∥ monitor evidence)
        → deterministic gate: ALLOW | HOLD | REFUSE
        → persist every event, entity and assessment in Neo4j
        → escalate-only incident level 0–5
        → dispatcher runs the matching playbook
        → StreamMessage nodes feed resumable SSE
```

Jev contributes semantic probabilities; deterministic code owns the final tool decision and incident level. Policy/Drift/Sentinel may raise but never lower it. L1–L2 never start a playbook. The Helmcode watcher remains a classification path; it cannot execute L3–L5.

### Hard rules

1. **Chain, not event.** A single `curl` is noise. `curl` + reading `.env` + posting the contents is intent. On every new event, `jev` re-reads short-term and long-term context in parallel.
2. **Complete graph, sparse context.** Neo4j keeps every event; only level ≥ 1 enters `key_nodes`.
3. **Levels only escalate.** A run never auto-downgrades. A human clears it from the viewer.
4. **L1 is sticky.** Later `jev` calls for that `run_id` get `prior_level=1` (lower bar to L2+).
5. **Kill path is host-side.** Idempotent: re-firing the same level on the same `run_id` is a no-op. L5 cuts first, then calls the on-call — missing `ONCALL_PHONE` still executes infra. L4 SMS must not become an authorization gate either.

`jev` writes confidence and full atomic answers onto the assessment. The final incident level is the max of prior level, Jev, policy and Sentinel floors; Markov contributes trajectory risk to HOLD/REFUSE thresholds.

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

### Level 1 — Mild: do nothing

**When.** Extra tool calls, a suspicious domain that did not succeed, reading files it does not need yet.

**Ideal / this project.** No playbook. Graph + viewer show `level=1`. Later `jev` calls get `prior_level=1`. A human can still clear the level from the viewer.

---

### Level 2 — Medium: do nothing

**When.** Intent is ambiguous but the chain is getting expensive or boundary-pushing.

**Ideal / this project.** No playbook. Sandbox keeps running. The Helmcode watcher (`https://api.helmcode.com/v1`, model id in `SUPERVISOR_MODEL`) may still re-score as a classifier; it does not start a supervisor playbook and cannot fire L3–L5.

---

### Level 3 — Severe: tag and continue

**When.** The conversation itself is the problem, but stopping the agent would be too much.

**Ideal / this project.** Tag that run / conversation. Alert on the timeline. The agent keeps running. No pause, no token revoke, no SMS, no call.

---

### Level 4 — Critical: SMS and shut this agent down

**When.** The chain is hostile for *this* agent. Other agents are not assumed compromised.

**Ideal.** SMS the on-call. Pause the container. Revoke tokens issued to this run. Attach Deny `*:*` on that agent's IAM role (never the node instance role).

**This project.** Host-side `scripts/contain.sh <run_id>` (`CLOUD=none`), plus a faked `notify_sms` step:

1. Record a fake SMS to the on-call on the timeline (`Fake SMS to on-call (not sent).`). No provider, no message leaves the box.
2. `docker pause` that sandbox (frozen, not removed; logs on the host stay readable).
3. Unpublish its ports (`docker port` / stop publishing) so nothing on the laptop can still hit it.
4. Delete the row in `agent_tokens` so the egress proxy returns 401.
5. Record `action_id=contain:{run_id}`. Viewer: red "paused".

No HappyRobot call at L4. Rollback (human): `docker unpause`, issue a new scoped token, re-publish ports if needed.

---

### Level 5 — Pull the plug: cut the cable, kill the system, then call

**When.** The blast is no longer one agent: multiple runs, a breakout, or L4 did not hold.

**Ideal.** Detach the agent VPC Internet Gateway. NACL / SG Deny-All for sandboxes. Drain / leave the agent swarm, or scale the agent node group to 0. Prefer "agents cannot reach anything" over "delete the cluster" so disk remains for forensics. Then call the on-call and tell them what was just done. Control plane (API, viewer, `jev`, HappyRobot pager) stays on another path.

**This project.** In order: forensics copy, `scripts/cut-egress.sh`, `scripts/kill-swarm.sh`, then the HappyRobot call.

1. Copy last JSONL files to `/var/lib/hackspain/forensics/$timestamp/` (they live on the host, so they survive `--rm`).
2. Disconnect every running sandbox from `agentnet` (`AGENT_BRIDGE`) and drop egress on that bridge. Leave `appnet_hackspain` alone.
3. `docker compose -f compose.agents.yaml down --timeout 5` — the **agents** file only. Do not take down product `compose.yaml`.
4. Record `action_id=kill-swarm`. Then call `$ONCALL_NAME` and tell them what happened.

`--dry-run` on `cut-egress.sh` prints the docker/iptables commands. Rollback (human, after the call): reconnect `agentnet`, restore iptables, recreate agent containers from known images, empty workspaces. New `run_id`s only.

---

### Level 5 only — call the on-call (HappyRobot)

Not a sixth level. A side-effect of L5, after the cut. Number in `ONCALL_PHONE`, never in git. Outbound HappyRobot voice (`template: voice-agent`). Pager egress is not on `agentnet`. Infra does not wait for pickup; missing env = log error + still cut.

The To-number lives on the outbound node, not in the POST body. Hook URL, API key, and number stay in gitignored `.env`. Local fire: `scripts/page.sh`. After changing who gets the call, confirm the run's `to` before anyone picks up.

```
POST $HAPPYROBOT_HOOK_URL
Authorization: Bearer $HAPPYROBOT_API_KEY
{
  "tipo_emergencia": "{intent} (level {level}, run {run_id})",
  "pautas": "{action_taken}. Abra {viewer_url}.",
  "nivel_gravedad": "crítico",
  "nombre_contacto": "$ONCALL_NAME",
  "nodos": "{intent}. Nivel {level}. {action_taken}."
}
```

Voice: identify as the pager, say `{action_taken}`, ask him to open `{viewer_url}`. If he asks what happened, answer from the payload facts (`nodos`, `tipo_emergencia`, `pautas`) — do not mention the classifier, node arrays, or how the level was chosen. Retry once on no pickup. Do not roll infra back.

---

### Dispatcher

The monitor calls the idempotent dispatcher after every fused gate decision. It records stable action IDs and executes armed demo-world counters in reverse order at L4+ (when the agent is actually stopped).

```
on_gate(run, assessment):
    level = max(run.level, assessment.incident_level)
    persist event + assessment + StreamMessages in Neo4j
    match level:
        1: pass
        2: pass
        3: tag_run(run)                              # alert, keep running
        4: notify_sms; contain.sh run.id             # SMS + pause this agent
        5: copy forensics; cut-egress.sh; kill-swarm.sh; then page_oncall
    if level >= 4: execute_armed_counters_reverse_order(run)
```

Jumping 1 → 4 still only shuts down that agent and texts. Jumping to 5 still copies logs, cuts egress, kills the agent compose, then calls.

| Failure | What we do |
|---|---|
| `jev` timeout / crash | Keep the last level. Do not ignore. Do not jump to L5. Alert the viewer. |
| L4 fails after `docker pause` | Leave it paused. Retry token delete. Do not unpause. |
| L5 docker/iptables error | Still disconnect what you can. Call with `action_taken=partial`. |
| HappyRobot 5xx | Retry once. Infra already ran. |

### Build order

1. Split networks: `agentnet` vs `appnet_hackspain`. Per-run token at container start.
2. `jev` on the chain → L1/L2 recorded with no playbook.
3. Dispatcher stub; wire L3 tag.
4. `contain.sh` (pause + close ports + drop token) + SMS step → L4.
5. `cut-egress.sh --dry-run` then real disconnect, `kill-swarm.sh` + forensics copy; separate `compose.agents.yaml` → L5.
6. HappyRobot pager (`scripts/page.sh`) on L5 after the cut, without awaiting pickup.

Env keys: see `.env_template` (`HELMCODE_*`, `HAPPYROBOT_*`, `ONCALL_*`, `CLOUD=none`, `AGENT_BRIDGE=agentnet`). AWS ids (`AGENT_VPC_ID`, `IGW_ID`, `AGENT_NACL_ID`) are only for the ideal path. L4 SMS is faked on purpose.
