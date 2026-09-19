import type { ActionMode, ActionTransition } from "./types";

export function newestActions(actions: ActionTransition[]): ActionTransition[] {
  return [...actions].reverse().slice(0, 20);
}

export function actionModeLabel(mode: ActionMode): string {
  return mode === "simulated" ? "SIMULATED" : "REAL";
}
