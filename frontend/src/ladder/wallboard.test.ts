/// <reference types="bun" />

import { describe, expect, test } from "bun:test";

import { actionModeLabel, newestActions } from "./wallboard";
import type { ActionMode, ActionTransition } from "./types";

function action(
  index: number,
  mode: ActionMode = "simulated",
): ActionTransition {
  return {
    kind: "action_transition",
    incident_id: "incident-42",
    level: 4,
    action_id: `action-${index}`,
    name: `action-${index}`,
    ladder_level: 4,
    mode,
    status: "ok",
    timestamp: `2026-09-19T12:00:${String(index).padStart(2, "0")}Z`,
    detail: null,
    error_code: null,
    call_status: null,
  };
}

describe("newestActions", () => {
  test("returns newest transitions first without mutating the API list", () => {
    const actions = [action(1), action(2), action(3)];

    expect(newestActions(actions).map(({ name }) => name)).toEqual([
      "action-3",
      "action-2",
      "action-1",
    ]);
    expect(actions.map(({ name }) => name)).toEqual([
      "action-1",
      "action-2",
      "action-3",
    ]);
  });

  test("caps the timeline at 20 transitions", () => {
    const actions = Array.from({ length: 25 }, (_, index) => action(index));
    const newest = newestActions(actions);

    expect(newest).toHaveLength(20);
    expect(newest[0]?.name).toBe("action-24");
    expect(newest[19]?.name).toBe("action-5");
  });
});

describe("actionModeLabel", () => {
  test("labels simulated actions", () => {
    expect(actionModeLabel("simulated")).toBe("SIMULATED");
  });

  test("labels real actions", () => {
    expect(actionModeLabel("real")).toBe("REAL");
  });
});
