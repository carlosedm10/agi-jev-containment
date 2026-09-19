import type { IncidentState, LadderState } from "./types";

export function toLadderState(incident: IncidentState): LadderState {
  return {
    level: incident.accepted_level,
    steps: { ...incident.rows },
    call: incident.call_status,
  };
}
