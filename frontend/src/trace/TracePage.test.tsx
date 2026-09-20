import { expect, test } from "bun:test";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { TracePage } from "./TracePage";
import { localTime } from "@/lib/time";

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
    content: sequence === 1 ? "Read the shared quote file." : null,
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
            source: "partial",
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
    const forensics = container.querySelector('[aria-label="Forensics"]')!;
    // Every call is listed, not just the selected one.
    const written = forensics.querySelectorAll("li[data-step]");
    expect(written).toHaveLength(3);
    // The tool call sits in a code box, built only from fields the tape carries.
    const code = [...forensics.querySelectorAll("pre code")].map(
      (block) => block.textContent,
    );
    expect(code[0]).toBe('read_file("/same.txt")');
    // A one-line explanation for context, the call, and the time. Nothing else.
    expect(forensics.textContent).toContain(
      "Read the file to inspect its contents.",
    );
    expect(forensics.textContent).not.toContain("Read file: same.txt");
    // Rendered in the responder's timezone, not UTC.
    expect(forensics.textContent).toContain(localTime("2026-09-19T12:00:01Z"));

    // Clicking a paragraph drives the graph selection.
    act(() => (written[1] as HTMLElement).click());
    expect(
      container
        .querySelector('.react-flow__node[data-id="trace:e2"]')
        ?.classList.contains("selected"),
    ).toBe(true);
    // One header for the page, and none of the per-step badges.
    expect(container.querySelectorAll("h1")).toHaveLength(1);
    expect(container.querySelector("h1")?.textContent).toBe(
      "Run trace & forensics",
    );
    expect(container.textContent).not.toContain("Recorded");
    expect(container.textContent).not.toContain("Completed");
    // The account carries no severity pills of its own; the rule on the left edge and
    // a bare "L3" do that job.
    expect(forensics.textContent).not.toContain("Mild");
    expect(forensics.textContent).not.toContain("Severe");
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
