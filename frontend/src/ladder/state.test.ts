/// <reference types="bun" />

import { describe, expect, test } from "bun:test";

import { toLadderState } from "./state";
import type { CallStatus, IncidentState, StepStatus } from "./types";

function incident(overrides: Partial<IncidentState> = {}): IncidentState {
  return {
    incident_id: "incident-42",
    accepted_level: 0,
    rows: {
      1: "idle",
      2: "idle",
      3: "idle",
      4: "idle",
      5: "idle",
    },
    actions: [],
    pager_status: "idle",
    call_status: "idle",
    updated_at: null,
    ...overrides,
  };
}

describe("toLadderState", () => {
  test("preserves reached lower rows that are still idle", () => {
    const state = toLadderState(
      incident({
        accepted_level: 4,
        rows: { 1: "idle", 2: "idle", 3: "running", 4: "running", 5: "idle" },
      }),
    );

    expect(state.steps[1]).toBe("idle");
    expect(state.steps[2]).toBe("idle");
  });

  test("maps an L2 tag transition onto the L1 row", () => {
    const state = toLadderState(
      incident({
        accepted_level: 2,
        rows: { 1: "ok", 2: "running", 3: "idle", 4: "idle", 5: "idle" },
      }),
    );

    expect(state.steps[1]).toBe("ok");
    expect(state.steps[2]).toBe("running");
  });

  test("maps L4 contain-all progress onto the L3 row", () => {
    const state = toLadderState(
      incident({
        accepted_level: 4,
        rows: { 1: "idle", 2: "idle", 3: "partial", 4: "running", 5: "idle" },
      }),
    );

    expect(state.steps[3]).toBe("partial");
    expect(state.steps[4]).toBe("running");
  });

  test("preserves a canceled supervisor row", () => {
    const state = toLadderState(
      incident({
        accepted_level: 3,
        rows: { 1: "ok", 2: "canceled", 3: "running", 4: "idle", 5: "idle" },
      }),
    );

    expect(state.steps[2]).toBe("canceled");
  });

  test("uses call status independently from pager action status", () => {
    const state = toLadderState(
      incident({
        accepted_level: 4,
        pager_status: "failed",
        call_status: "answered",
      }),
    );

    expect(state.call).toBe("answered");
  });

  test("preserves every call status", () => {
    const statuses: CallStatus[] = [
      "idle",
      "queued",
      "ringing",
      "answered",
      "no_pickup",
      "hung_up",
      "failed",
    ];

    expect(
      statuses.map(
        (call_status) => toLadderState(incident({ call_status })).call,
      ),
    ).toEqual(statuses);
  });

  test("accepts every API row status", () => {
    const statuses: StepStatus[] = [
      "idle",
      "running",
      "ok",
      "partial",
      "failed",
      "canceled",
    ];

    for (const status of statuses) {
      expect(
        toLadderState(
          incident({
            rows: { 1: status, 2: "idle", 3: "idle", 4: "idle", 5: "idle" },
          }),
        ).steps[1],
      ).toBe(status);
    }
  });
});
