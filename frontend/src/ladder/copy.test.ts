/// <reference types="bun" />

import { describe, expect, test } from "bun:test";

import {
  ACTION_STATUS_LABEL,
  CALL_LABEL,
  callRailLevel,
  ROWS,
  STEP_LABEL,
} from "./copy";

describe("ladder copy", () => {
  test("keeps pull the plug last", () => {
    expect(ROWS.map((row) => row.n)).toEqual([1, 2, 3, 4, 5]);
    expect(ROWS[4]?.title).toBe("Pull the plug");
  });

  test("labels states in English", () => {
    expect(STEP_LABEL.ok).toBe("Done");
    expect(STEP_LABEL.canceled).toBe("Canceled");
    expect(CALL_LABEL.ringing).toBe("Ringing");
    expect(CALL_LABEL.answered).toBe("Answered");
    expect(CALL_LABEL.failed).toBe("Failed");
    expect(ACTION_STATUS_LABEL.ok).toBe("Done");
  });

  test("parks the call rail on L5 only", () => {
    expect(callRailLevel(3)).toBeNull();
    expect(callRailLevel(4)).toBeNull();
    expect(callRailLevel(5)).toBe(5);
  });
});
