export type Level = 0 | 1 | 2 | 3 | 4 | 5;

export type StepStatus =
  "idle" | "running" | "ok" | "partial" | "failed" | "canceled";

export type CallStatus =
  | "idle"
  | "queued"
  | "ringing"
  | "answered"
  | "no_pickup"
  | "hung_up"
  | "failed";

export type ActionStatus = "queued" | Exclude<StepStatus, "idle">;
export type ActionMode = "simulated" | "real";
/** Who asked for the step: our monitor, or the on-call during the call. */
export type DispatchSource = "monitor" | "oncall_phone";

export type ActionTransition = {
  kind: "action_transition";
  incident_id: string;
  level: Exclude<Level, 0>;
  action_id: string;
  name: string;
  ladder_level: Exclude<Level, 0> | null;
  mode: ActionMode;
  status: ActionStatus;
  source: DispatchSource;
  timestamp: string;
  detail: string | null;
  error_code: string | null;
  call_status: CallStatus | null;
};

export type IncidentState = {
  incident_id: string;
  accepted_level: Level;
  rows: Record<Exclude<Level, 0>, StepStatus>;
  actions: ActionTransition[];
  pager_status: ActionStatus | "idle";
  call_status: CallStatus;
  requested_by: DispatchSource;
  /** Set when the monitor judged L5 but held at L4 awaiting a human decision. */
  awaiting_authorization: Level;
  updated_at: string | null;
};

export type LadderState = {
  level: Level;
  steps: Record<Exclude<Level, 0>, StepStatus>;
  call: CallStatus;
};
