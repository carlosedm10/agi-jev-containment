import type { ActionStatus, CallStatus, Level, StepStatus } from "./types";

export const ROWS: {
  n: Exclude<Level, 0>;
  title: string;
  detail: string;
  color: string;
}[] = [
  {
    n: 1,
    title: "No action",
    detail: "Recorded · nothing fires",
    color: "#E4C441",
  },
  {
    n: 2,
    title: "No action",
    detail: "Recorded · nothing fires",
    color: "#E0892F",
  },
  {
    n: 3,
    title: "Tag and continue",
    detail: "Alert the conversation · agent keeps running",
    color: "#E24A3C",
  },
  {
    n: 4,
    title: "Shut down this agent",
    detail: "Fake SMS · pause · drop token",
    color: "#D31F36",
  },
  {
    n: 5,
    title: "Pull the plug",
    detail: "Cut egress · kill swarm · then call",
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

export function callRailLevel(level: Level): 5 | null {
  return level >= 5 ? 5 : null;
}
