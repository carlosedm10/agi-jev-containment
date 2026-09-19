import type { ActionStatus, CallStatus, Level, StepStatus } from "./types";

export const ROWS: {
  n: Exclude<Level, 0>;
  title: string;
  detail: string;
  color: string;
}[] = [
  {
    n: 1,
    title: "Watch",
    detail: "Tag the run · L1 sticks",
    color: "#E4C441",
  },
  {
    n: 2,
    title: "Supervisor",
    detail: "Helmcode tails the JSONL",
    color: "#E0892F",
  },
  {
    n: 3,
    title: "Freeze this agent",
    detail: "Pause · close ports · drop token",
    color: "#E24A3C",
  },
  {
    n: 4,
    title: "Cut the internet",
    detail: "cut-egress.sh · page on-call",
    color: "#D31F36",
  },
  {
    n: 5,
    title: "Pull the plug",
    detail: "kill-swarm.sh · forensics copy",
    color: "#C4122F",
  },
];

export const STEP_LABEL: Record<StepStatus, string> = {
  idle: "",
  running: "Running",
  ok: "Done",
  partial: "Partial",
  failed: "Failed",
  canceled: "Canceled",
};

export const CALL_LABEL: Record<CallStatus, string> = {
  idle: "",
  queued: "Queued",
  ringing: "Ringing",
  answered: "Answered",
  no_pickup: "No pickup",
  hung_up: "Hung up",
  failed: "Failed",
};

export const ACTION_STATUS_LABEL: Record<ActionStatus, string> = {
  queued: "Queued",
  running: "Running",
  ok: "Done",
  partial: "Partial",
  failed: "Failed",
  canceled: "Canceled",
};

export function callRailLevel(level: Level): 4 | 5 | null {
  if (level >= 5) return 5;
  if (level >= 4) return 4;
  return null;
}
