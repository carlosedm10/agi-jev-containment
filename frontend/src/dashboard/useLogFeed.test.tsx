import { expect, test } from "bun:test";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { useLogFeed } from "./useLogFeed";

test("clearing logs rejects an in-flight old response and filters historical rows on future polls", async () => {
  const original = globalThis.fetch;
  const old = {
    id: "old",
    run_id: "previous",
    timestamp: "2020-01-01T00:00:00Z",
    kind: "file_read",
    level: 0,
  };
  let finishOld!: (response: Response) => void;
  let calls = 0;
  globalThis.fetch = (async () => {
    if (++calls === 1) return Response.json([old]);
    if (calls === 2)
      return new Promise<Response>((resolve) => {
        finishOld = resolve;
      });
    return Response.json([
      old,
      {
        ...old,
        id: "new",
        run_id: "new-run",
        timestamp: new Date().toISOString(),
      },
    ]);
  }) as unknown as typeof fetch;
  const container = document.createElement("div");
  const root = createRoot(container);
  let clear!: () => void;
  function Probe() {
    const feed = useLogFeed();
    clear = feed.clear;
    return (
      <>
        {feed.logs?.map((log) => (
          // The message no longer repeats the run id, so identify the row by its id.
          <p key={log.id}>{`${log.id} ${log.message}`}</p>
        ))}
      </>
    );
  }
  try {
    await act(async () => {
      root.render(<Probe />);
    });
    expect(container.textContent).toContain("previous");
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 550));
    });
    act(() => clear());
    expect(container.textContent).toBe("");
    await act(async () => {
      finishOld(Response.json([old]));
    });
    expect(container.textContent).toBe("");
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 550));
    });
    expect(container.textContent).not.toContain("previous");
    expect(container.textContent).toContain("new-run");
  } finally {
    act(() => root.unmount());
    globalThis.fetch = original;
  }
});

test("logs refresh for every run and keep repeated visits independently of graph focus", async () => {
  const original = globalThis.fetch;
  let polls = 0;
  const event = (run: string, id: string) => ({
    id,
    run_id: run,
    timestamp: "2026-09-19T12:00:00Z",
    kind: "file_read",
    level: 1,
  });
  globalThis.fetch = (async () =>
    Response.json(
      ++polls === 1
        ? [event("first", "e1")]
        : [event("second", "e1"), event("first", "e2"), event("first", "e1")],
    )) as unknown as typeof fetch;
  const container = document.createElement("div");
  const root = createRoot(container);
  function Probe() {
    const { logs } = useLogFeed();
    return (
      <>
        {logs?.map((log) => (
          <p key={log.id}>{`${log.id} ${log.message}`}</p>
        ))}
      </>
    );
  }
  try {
    await act(async () => {
      root.render(<Probe />);
    });
    expect(container.querySelectorAll("p")).toHaveLength(1);
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 550));
    });
    expect(container.querySelectorAll("p")).toHaveLength(3);
    // The run id identifies the row but is no longer repeated inside the line.
    expect(container.textContent).toContain("second");
    expect(container.textContent).not.toContain('"run_id"');
    expect(container.textContent).toContain("stdout F");
  } finally {
    act(() => root.unmount());
    globalThis.fetch = original;
  }
});
