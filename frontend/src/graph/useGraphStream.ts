import { useEffect, useRef, useState } from "react";

import {
  applyUpdate,
  fromSnapshot,
  parseSnapshot,
  parseUpdate,
  type Graph,
} from "@/graph/protocol";

export const STREAM_URL = "/api/graph/stream";
export const RECONNECT_DELAY_MS = 1000;

export type GraphStreamStatus = "connecting" | "live" | "reconnecting";

export type GraphStream = {
  graph: Graph | null;
  status: GraphStreamStatus;
  error: string | null;
};

export function useGraphStream(url: string = STREAM_URL): GraphStream {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [status, setStatus] = useState<GraphStreamStatus>("connecting");
  const [error, setError] = useState<string | null>(null);
  const current = useRef<Graph | null>(null);

  useEffect(() => {
    let source: EventSource | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let done = false;

    const store = (next: Graph | null) => {
      current.current = next;
      setGraph(next);
    };

    const resync = (reason: string) => {
      if (done) return;
      source?.close();
      source = null;
      store(null);
      setStatus("reconnecting");
      setError(reason);
      retry = setTimeout(connect, RECONNECT_DELAY_MS);
    };

    const onSnapshot = (data: string) => {
      const snapshot = parseSnapshot(data);
      if (snapshot === null) return resync("invalid snapshot");
      store(fromSnapshot(snapshot));
      setStatus("live");
      setError(null);
    };

    const onUpdate = (data: string) => {
      const update = parseUpdate(data);
      if (update === null) return resync("invalid update");
      if (current.current === null) return resync("update before snapshot");
      const next = applyUpdate(current.current, update);
      if (next === null) return resync("revision gap");
      store(next);
    };

    function connect() {
      retry = null;
      const opened = new EventSource(url);
      source = opened;
      opened.addEventListener("snapshot", (event) =>
        onSnapshot((event as MessageEvent<string>).data),
      );
      opened.addEventListener("update", (event) =>
        onUpdate((event as MessageEvent<string>).data),
      );
      opened.addEventListener("error", () => resync("stream closed"));
    }

    connect();

    return () => {
      done = true;
      if (retry !== null) clearTimeout(retry);
      source?.close();
      current.current = null;
    };
  }, [url]);

  return { graph, status, error };
}
