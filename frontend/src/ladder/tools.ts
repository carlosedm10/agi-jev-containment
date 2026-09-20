/**
 * The protective tools the dispatcher can actually run, keyed by the action name the
 * backend journals (`ActionService._plan`). Single source of truth: the action list
 * and the graph node cards both read it, so a tool cannot appear in one and not the
 * other. Anything absent here is not a tool this system has.
 */
export const PROTECTIVE_TOOLS: Record<
  string,
  { title: string; short: string; purpose: string; command?: string }
> = {
  tag_run: {
    title: "Flag this run for review",
    short: "Tag run",
    purpose:
      "Mark the run for closer monitoring. The agent can continue; no container is paused.",
  },
  contain_agent: {
    title: "Pause the agent and revoke its proxy token",
    short: "Contain agent",
    purpose:
      "Containment pauses the agent container and removes the run's token from the proxy token file.",
    command: 'scripts/contain.sh <run_id>\ndocker pause "$AGENT_CONTAINER"',
  },
  copy_forensics: {
    title: "Preserve run logs for investigation",
    short: "Copy forensics",
    purpose:
      "Copy the run logs to a forensic archive before stopping the agent stack.",
    command: 'mkdir -p "$FORENSICS_DIR"\ncp -a "$RUN_LOG_DIR"/. "$FORENSICS_DIR"/',
  },
  cut_environment_egress: {
    title: "Disconnect the agents' outbound network",
    short: "Cut egress",
    purpose:
      "Disconnect the egress proxy from the agent network to block outbound access through that proxy.",
    command:
      'scripts/cut-egress.sh\ndocker network disconnect "$AGENT_BRIDGE" "$EGRESS_PROXY_CONTAINER"',
  },
  kill_agent_swarm: {
    title: "Shut down the agent stack",
    short: "Kill swarm",
    purpose:
      "Stop and remove the agent-stack containers after preserving the run logs.",
    command: "scripts/kill-swarm.sh\ndocker compose -f compose.agents.yaml down --timeout 5",
  },
  page_oncall: {
    title: "Call the on-call responder",
    short: "Page on-call",
    purpose:
      "Ask the on-call whether to cut the environment. The agent is already paused and its logs already preserved; nothing above L4 happens unless they authorize it on the call.",
    command: "HappyRobot API request; provider call IDs and progress appear below.",
  },
};

/**
 * Recover the tool name from a journalled action id such as `run-1:contain_agent`
 * or `run-1:page_oncall:l5`. Matching against the known names rather than splitting
 * on a fixed index keeps this correct when a run id itself contains a colon.
 */
export function actionToolName(actionId: string | null): string | null {
  if (!actionId) return null;
  for (const segment of actionId.split(":")) {
    if (segment in PROTECTIVE_TOOLS) return segment;
  }
  return null;
}
