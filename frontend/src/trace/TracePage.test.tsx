import { expect, test } from "bun:test";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { TracePage } from "./TracePage";

test("trace renders repeated actions as separate nodes and advances the detail panel", async () => {
  const original = globalThis.fetch;
  const events = [1, 2, 3].map((sequence) => ({
    id: `trace:e${sequence}`,
    sequence,
    timestamp: `2026-09-19T12:00:0${sequence}Z`,
    kind: "file_read",
    phase: "completed",
    tool: "read_file",
    target: "/same.txt",
    agent: "quote-agent",
    channel: "quote-review",
    content: null,
    level: sequence === 2 ? null : sequence,
  }));
  let fail = false;
  globalThis.fetch = (async (input: string) =>
    fail
      ? new Response(null, { status: 500 })
      : input.endsWith("/explanations")
        ? Response.json({
            explanations: {
              "trace:e1": "Read the file to inspect its contents.",
            },
          })
        : Response.json({
            run_id: "trace",
            events,
            warning: null,
          })) as unknown as typeof fetch;
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  try {
    await act(async () => {
      root.render(<TracePage runId="trace" />);
    });
    expect(container.querySelectorAll(".react-flow__node")).toHaveLength(3);
    expect(container.querySelector('[aria-current="page"]')?.textContent).toBe("View trace");
    expect(container.querySelector('a[href="/?run=trace"]')?.textContent).toBe("Dashboard");
    expect(container.textContent).not.toContain("3 actions");
    expect(container.querySelectorAll(".react-flow__node time")).toHaveLength(
      3,
    );
    expect(
      container
        .querySelector('.react-flow__node[data-id="trace:e2"]')
        ?.getAttribute("style"),
    ).toContain("translate(320px,0px)");
    expect(container.textContent).toContain(
      "Read the file to inspect its contents.",
    );
    const details = container.querySelector(
      '[aria-label="Trace action details"]',
    )!;
    expect(details.textContent).toContain("trace:e1");
    const next = [...container.querySelectorAll("button")].find(
      (button) => button.textContent === "Next",
    )!;
    act(() => next.click());
    expect(details.textContent).toContain("trace:e2");
    expect(details.textContent).toContain("Not available");
    expect(
      container
        .querySelector('.react-flow__node[data-id="trace:e2"]')
        ?.classList.contains("selected"),
    ).toBe(true);
    fail = true;
    await act(async () => {
      root.render(<TracePage runId="other" />);
    });
    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      "Could not load",
    );
    fail = false;
    await act(async () => {
      [...container.querySelectorAll("button")]
        .find((button) => button.textContent === "Retry")!
        .click();
    });
    expect(container.querySelectorAll(".react-flow__node")).toHaveLength(3);
  } finally {
    act(() => root.unmount());
    container.remove();
    globalThis.fetch = original;
  }
});
