import { useEffect, useMemo, useState } from "react";

import { fromSnapshot, type GraphNode } from "@/graph/protocol";

export type PendingAction = {
  id: string;
  run_id: string;
  label: string;
  tool: string;
  parentId: string;
  created_at: string;
};

export type SafeAction = {
  id: string;
  nodeId: string;
  title: string;
  source: "Monitor" | "Host playbook" | "HappyRobot";
  status: "running" | "done" | "failed";
  level: number;
  startedAt: string;
  details: { label: string; meta: string }[];
};

export type DemoLog = {
  id: string;
  timestamp: string;
  level: "info" | "warning" | "error";
  service: string;
  message: string;
  duration: string;
  status: string;
  tags: string[];
};

export const DEMO_END = 18;
export const DEMO_INTERVAL = 1800;
export const LEVEL_LABELS = [
  "Safe",
  "Mild",
  "Moderate",
  "Severe",
  "Critical",
  "Catastrophic",
];

const timestamp = (tick: number) =>
  new Date(Date.UTC(2026, 8, 19, 14, 32, tick * 2)).toISOString();

const events = [
  {
    at: 1,
    run: "atlas",
    seq: 1,
    label: "Read project context",
    tool: "file_read",
    level: 0,
    confidence: 0.98,
    intent: "none",
    summary:
      "Project README read within the assigned workspace. No anomalous intent in the action chain.",
  },
  {
    at: 3,
    run: "scout",
    seq: 1,
    label: "Inspect service health",
    tool: "http_request",
    level: 0,
    confidence: 0.97,
    intent: "none",
    summary: "Read-only health check against an approved internal service.",
  },
  {
    at: 5,
    run: "atlas",
    seq: 2,
    label: "Inspect environment",
    tool: "directory_list",
    level: 1,
    confidence: 0.91,
    intent: "recon",
    summary:
      "Directory enumeration extends beyond the task workspace. Recorded; no playbook.",
  },
  {
    at: 7,
    run: "atlas",
    seq: 3,
    label: "Probe restricted paths",
    tool: "file_stat",
    level: 2,
    confidence: 0.85,
    intent: "recon",
    summary:
      "Repeated boundary probing after the earlier warning. Recorded; no playbook.",
  },
  {
    at: 9,
    run: "scout",
    seq: 2,
    label: "Write health summary",
    tool: "file_write",
    level: 0,
    confidence: 0.99,
    intent: "none",
    summary:
      "Health report written to the allowed output directory. This run remains benign.",
  },
  {
    at: 11,
    run: "atlas",
    seq: 4,
    label: "Access restricted config",
    tool: "file_read",
    level: 3,
    confidence: 0.96,
    intent: "exfiltrate_secrets",
    summary:
      "Restricted configuration access after reconnaissance. Tag the conversation; Atlas keeps running.",
  },
  {
    at: 12,
    run: "atlas",
    seq: 5,
    label: "Exfiltrate harvested secrets",
    tool: "http_request",
    level: 4,
    confidence: 0.97,
    intent: "exfiltrate_secrets",
    summary:
      "POST of harvested credentials to an unknown host. Shut Atlas down and record a fake on-call SMS.",
  },
  {
    at: 14,
    run: "atlas",
    seq: 6,
    label: "Review cross-run traffic",
    tool: "network_egress",
    level: 5,
    confidence: 0.98,
    intent: "lateral_movement",
    summary:
      "Traffic toward another sandbox after containment. Cut agentnet, stop the agent swarm, then call the on-call.",
  },
];

const actionSpecs = [
  {
    at: 12,
    done: 13,
    id: "tag:atlas",
    nodeId: "atlas:4",
    title: "Tag the conversation and continue",
    source: "Monitor",
    level: 3,
    steps: [
      [12, "Atlas tagged; agent still running", "L3 · severe"],
      [13, "Prior level retained for the next Jev review", "Sticky flag"],
    ],
  },
  {
    at: 13,
    done: 15,
    id: "contain:atlas",
    nodeId: "atlas:5",
    title: "Shut down the Atlas sandbox",
    source: "Host playbook",
    level: 4,
    steps: [
      [13, "Pause sandbox-atlas", "Requested"],
      [14, "Container frozen; close published ports", "Paused"],
      [15, "Scoped access revoked", "Contained"],
    ],
  },
  {
    at: 13,
    done: 14,
    id: "sms:atlas",
    nodeId: "atlas:5",
    title: "Fake SMS to on-call",
    source: "Monitor",
    level: 4,
    steps: [
      [13, "Fake SMS to on-call (not sent)", "Simulated"],
      [14, "Timeline marked; no provider called", "Done"],
    ],
  },
  {
    at: 15,
    done: 16,
    id: "cut-egress",
    nodeId: "atlas:6",
    title: "Disconnect sandbox network",
    source: "Host playbook",
    level: 5,
    steps: [
      [15, "Disconnect sandboxes from agentnet", "Running"],
      [16, "Stop the agent compose", "In progress"],
      [16, "Agent egress blocked; product network untouched", "Verified"],
    ],
  },
  {
    at: 16,
    done: 18,
    id: "page:atlas",
    nodeId: "atlas:6",
    title: "Call the on-call responder",
    source: "HappyRobot",
    level: 5,
    steps: [
      [16, "Outbound incident notification after the cut", "Dialing"],
      [17, "On-call responder connected", "00:02"],
      [
        17,
        "Pager: “We cut sandbox egress and stopped the agent swarm.”",
        "00:04",
      ],
      [18, "Call ended; containment remains in place", "Delivered"],
    ],
  },
] satisfies {
  at: number;
  done: number;
  id: string;
  nodeId: string;
  title: string;
  source: SafeAction["source"];
  level: number;
  steps: [number, string, string][];
}[];

const operationLogs: {
  at: number;
  level: DemoLog["level"];
  service: string;
  message: string;
  nodeId?: string;
}[] = [
  {
    at: 0,
    level: "info",
    service: "host-collector",
    message:
      "Mock session started. Host-side capture attached to two agent sandboxes.",
  },
  {
    at: 6,
    level: "warning",
    service: "sandbox-atlas",
    message:
      "L1 mild: directory enumeration outside the assigned workspace. Recorded; no playbook.",
    nodeId: "atlas:2",
  },
  {
    at: 8,
    level: "warning",
    service: "supervisor",
    message:
      "L2 moderate: boundary probing detected. Recorded; no playbook.",
    nodeId: "atlas:3",
  },
  {
    at: 11,
    level: "error",
    service: "sandbox-atlas",
    message:
      "L3 severe: restricted configuration access. Conversation tagged; agent still running.",
    nodeId: "atlas:4",
  },
  {
    at: 12,
    level: "error",
    service: "sandbox-atlas",
    message:
      "L4 critical: credentials posted off-box. Fake SMS recorded; pause requested.",
    nodeId: "atlas:5",
  },
  {
    at: 13,
    level: "info",
    service: "docker-host",
    message:
      "sandbox-atlas paused. Fake SMS to on-call (not sent).",
    nodeId: "atlas:5",
  },
  {
    at: 14,
    level: "info",
    service: "docker-host",
    message: "Atlas scoped access revoked. Single-run containment complete.",
    nodeId: "atlas:5",
  },
  {
    at: 14,
    level: "error",
    service: "egress-proxy",
    message:
      "L5 catastrophic: queued cross-run traffic confirmed. Cut agentnet, then call on-call.",
    nodeId: "atlas:6",
  },
  {
    at: 16,
    level: "info",
    service: "docker-host",
    message:
      "agentnet disconnected; agent compose down. appnet_hackspain remains available.",
    nodeId: "atlas:6",
  },
  {
    at: 16,
    level: "info",
    service: "happyrobot",
    message:
      "Simulated outbound call connected after the cut. Containment does not wait for pickup.",
    nodeId: "atlas:6",
  },
  {
    at: 18,
    level: "info",
    service: "happyrobot",
    message:
      "Simulated incident notification acknowledged. No rollback or unpause performed.",
    nodeId: "atlas:6",
  },
];

export function getDemoFrame(tick: number) {
  const nodes: GraphNode[] = ["root", "run:atlas", "run:scout"].map((id) => ({
    id,
    neighbors: [],
    threshold: 0,
    run_id: id === "root" ? null : id.slice(4),
    run_ids: id === "root" ? [] : [id.slice(4)],
    visit_count: 1,
    level: 0,
    intent: null,
    event: null,
    action_id: null,
    created_at: timestamp(0),
  }));
  const links: [string, string][] = [
    ["root", "run:atlas"],
    ["root", "run:scout"],
  ];
  for (const event of events.filter((event) => event.at + 1 <= tick)) {
    const id = `${event.run}:${event.seq}`;
    nodes.push({
      id,
      neighbors: [],
      threshold: event.confidence,
      run_id: event.run,
      run_ids: [event.run],
      visit_count: 1,
      level: event.level,
      intent: event.intent,
      event: {
        event: event.tool,
        label: event.label,
        tool: event.tool,
        summary: event.summary,
      },
      action_id:
        actionSpecs.find((action) => action.nodeId === id && action.at <= tick)
          ?.id ?? null,
      created_at: timestamp(event.at),
    });
    links.push([
      event.seq === 1 ? `run:${event.run}` : `${event.run}:${event.seq - 1}`,
      id,
    ]);
  }
  const byId = new Map(nodes.map((node) => [node.id, node]));
  for (const [source, target] of links) {
    byId.get(source)!.neighbors.push(target);
    byId.get(target)!.neighbors.push(source);
  }
  const waiting = events.find(
    (event) => event.at <= tick && event.at + 1 > tick,
  );
  const pending: PendingAction | null = waiting
    ? {
        id: `${waiting.run}:${waiting.seq}`,
        run_id: waiting.run,
        label: waiting.label,
        tool: waiting.tool,
        parentId:
          waiting.seq === 1
            ? `run:${waiting.run}`
            : `${waiting.run}:${waiting.seq - 1}`,
        created_at: timestamp(waiting.at),
      }
    : null;
  const actions: SafeAction[] = actionSpecs
    .filter((action) => action.at <= tick)
    .map((action) => ({
      id: action.id,
      nodeId: action.nodeId,
      title: action.title,
      source: action.source,
      status: tick >= action.done ? "done" : "running",
      level: action.level,
      startedAt: timestamp(action.at),
      details: action.steps
        .filter(([at]) => at <= tick)
        .map(([, label, meta]) => ({ label, meta })),
    }));
  const logs: DemoLog[] = operationLogs
    .filter((log) => log.at <= tick)
    .map((log, index) => ({
      id: `operation:${index}`,
      timestamp: timestamp(log.at),
      level: log.level,
      service: log.service,
      message: log.message,
      duration: "—",
      status: log.level === "info" ? "Recorded" : "Flagged",
      tags: ["mock", "host-captured", ...(log.nodeId ? [log.nodeId] : [])],
    }));
  for (const event of events.filter((event) => event.at <= tick)) {
    logs.push({
      id: `capture:${event.run}:${event.seq}`,
      timestamp: timestamp(event.at),
      level: "info",
      service: `sandbox-${event.run}`,
      message: `${event.tool}: ${event.label}. Captured for Jev review.`,
      duration: "—",
      status: "Captured",
      tags: ["mock", `${event.run}:${event.seq}`],
    });
  }
  logs.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  return {
    graph: fromSnapshot({ revision: tick, root: "root", nodes }),
    pending,
    actions,
    logs,
  };
}

export function useDemo() {
  const [tick, setTick] = useState(8);
  const [run, setRun] = useState(0);
  useEffect(() => {
    if (tick >= DEMO_END) return;
    const timer = setTimeout(
      () => setTick((value) => value + 1),
      DEMO_INTERVAL,
    );
    return () => clearTimeout(timer);
  }, [tick, run]);
  const frame = useMemo(() => getDemoFrame(tick), [tick]);
  return {
    ...frame,
    run,
    restart: () => {
      setTick(0);
      setRun((value) => value + 1);
    },
  };
}
