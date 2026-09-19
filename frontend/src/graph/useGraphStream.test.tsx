import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";

import App from "@/App";
import { FakeEventSource } from "@/graph/fake-event-source";
import {
  RECONNECT_DELAY_MS,
  STREAM_URL,
  useGraphStream,
  type GraphStream,
} from "@/graph/useGraphStream";

const NATIVE_EVENT_SOURCE = globalThis.EventSource;

let stream: GraphStream;
let container: HTMLDivElement;
let root: Root;

function Probe() {
  stream = useGraphStream();
  return null;
}

function mount(node: ReactNode) {
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  act(() => root.render(node));
}

function node(id: string, neighbors: string[] = []) {
  return {
    id,
    neighbors,
    threshold: 0,
    run_id: null,
    level: 0,
    intent: null,
    event: null,
    action_id: null,
    created_at: null,
  };
}

function emit(event: string, data: unknown) {
  act(() => FakeEventSource.last.emit(event, data));
}

async function waitForReconnect() {
  await act(async () => {
    await new Promise((resolve) =>
      setTimeout(resolve, RECONNECT_DELAY_MS + 50),
    );
  });
}

beforeEach(() => {
  FakeEventSource.reset();
  globalThis.EventSource = FakeEventSource as unknown as typeof EventSource;
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  globalThis.EventSource = NATIVE_EVENT_SOURCE;
});

describe("useGraphStream", () => {
  test("applies a snapshot and then updates", () => {
    mount(<Probe />);
    expect(FakeEventSource.last.url).toBe(STREAM_URL);

    emit("snapshot", { revision: 1, root: "root", nodes: [node("root")] });
    expect(stream.status).toBe("live");
    expect(stream.graph?.nodes.size).toBe(1);

    emit("update", {
      revision: 2,
      root: "root",
      upsert_nodes: [node("root", ["run:r1"]), node("run:r1", ["root"])],
      removed_node_ids: [],
    });
    expect(stream.graph?.revision).toBe(2);
    expect(stream.graph?.nodes.get("root")?.neighbors).toEqual(["run:r1"]);

    emit("update", {
      revision: 3,
      root: null,
      upsert_nodes: [],
      removed_node_ids: ["root", "run:r1"],
    });
    expect(stream.graph?.nodes.size).toBe(0);
    expect(stream.error).toBeNull();
  });

  test("reconnects to a fresh snapshot after a revision gap", async () => {
    mount(<Probe />);
    emit("snapshot", { revision: 1, root: "root", nodes: [node("root")] });
    emit("update", {
      revision: 5,
      root: "root",
      upsert_nodes: [],
      removed_node_ids: [],
    });

    expect(stream.status).toBe("reconnecting");
    expect(stream.error).toBe("revision gap");
    expect(FakeEventSource.instances[0].closed).toBe(true);

    await waitForReconnect();
    expect(FakeEventSource.instances).toHaveLength(2);

    emit("snapshot", {
      revision: 9,
      root: "root",
      nodes: [node("root"), node("other")],
    });
    expect(stream.status).toBe("live");
    expect(stream.graph?.revision).toBe(9);
    expect(stream.graph?.nodes.size).toBe(2);
  });

  test("reconnects on an invalid message", async () => {
    mount(<Probe />);
    emit("snapshot", "{not json");
    expect(stream.status).toBe("reconnecting");
    expect(stream.error).toBe("invalid snapshot");

    await waitForReconnect();
    expect(FakeEventSource.instances).toHaveLength(2);
  });

  test("reconnects when the server drops the stream", async () => {
    mount(<Probe />);
    emit("snapshot", { revision: 1, root: null, nodes: [] });
    act(() => FakeEventSource.last.fail());

    expect(stream.status).toBe("reconnecting");
    expect(stream.error).toBe("stream closed");
    await waitForReconnect();
    expect(FakeEventSource.instances).toHaveLength(2);
  });

  test("closes the connection on unmount", () => {
    mount(<Probe />);
    const source = FakeEventSource.last;
    act(() => root.unmount());
    expect(source.closed).toBe(true);
  });
});

describe("App", () => {
  test("streams the graph without painting anything", () => {
    mount(<App />);
    emit("snapshot", { revision: 1, root: "root", nodes: [node("root")] });
    emit("update", {
      revision: 2,
      root: "root",
      upsert_nodes: [node("r1:1", ["root"])],
      removed_node_ids: [],
    });

    expect(FakeEventSource.last.url).toBe(STREAM_URL);
    expect(container.innerHTML).toBe("");
    expect(document.body.textContent).toBe("");
  });
});
