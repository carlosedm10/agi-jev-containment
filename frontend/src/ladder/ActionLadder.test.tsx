/// <reference types="bun" />

import { afterEach, describe, expect, test } from "bun:test";
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";

import { ActionLadder } from "./ActionLadder";
import type { LadderState } from "./types";

let container: HTMLDivElement;
let root: Root;

function mount(node: ReactNode) {
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  act(() => root.render(node));
}

function state(overrides: Partial<LadderState> = {}): LadderState {
  return {
    level: 0,
    steps: { 1: "idle", 2: "idle", 3: "idle", 4: "idle", 5: "idle" },
    call: "idle",
    ...overrides,
  };
}

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

describe("ActionLadder", () => {
  test("puts the ringing phone to the right of the live level", () => {
    mount(
      <ActionLadder
        state={state({
          level: 4,
          steps: { 1: "ok", 2: "canceled", 3: "ok", 4: "ok", 5: "idle" },
          call: "ringing",
        })}
      />,
    );

    const call = container.querySelector(".rung-l4 .rung-call");
    expect(call?.textContent).toContain("Ringing");
    expect(container.querySelector(".rung-l5 .rung-call")).toBeNull();
  });

  test("opens the kill-switch on L5 with the animated plug", () => {
    mount(
      <ActionLadder
        state={state({
          level: 5,
          steps: { 1: "ok", 2: "canceled", 3: "ok", 4: "ok", 5: "ok" },
          call: "answered",
        })}
      />,
    );

    expect(container.querySelector(".rungs")?.classList.contains("is-kill")).toBe(
      true,
    );
    expect(
      container.querySelector(".rung-l5 .killswitch")?.getAttribute("src"),
    ).toBe("/killswitch-icon.animated.svg");
    expect(container.querySelector(".rung-l5 .rung-call")?.textContent).toContain(
      "Answered",
    );
  });
});
