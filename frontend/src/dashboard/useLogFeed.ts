import { useCallback, useEffect, useRef, useState } from "react";
import { logsFromEvents, type TraceLogEvent } from "./feeds";
import type { Log } from "@/components/ui/interactive-logs-table";

export function useLogFeed() {
  const [logs, setLogs] = useState<Log[] | null>(null);
  const since = useRef<number | null>(null);
  const generation = useRef(0);
  const clear = useCallback(() => {
    since.current = Date.now();
    generation.current += 1;
    setLogs([]);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      const requestedGeneration = generation.current;
      try {
        const response = await fetch("/api/runs/logs/recent", {
          signal: controller.signal,
          cache: "no-store",
        });
        if (!response.ok) throw new Error("Logs unavailable");
        const events: TraceLogEvent[] = await response.json();
        if (
          !Array.isArray(events) ||
          !events.every(
            (event) =>
              event &&
              typeof event.id === "string" &&
              typeof event.run_id === "string" &&
              typeof event.timestamp === "string" &&
              typeof event.kind === "string",
          )
        )
          throw new Error("Invalid log feed");
        if (
          !controller.signal.aborted &&
          requestedGeneration === generation.current
        )
          setLogs(
            logsFromEvents(
              events.filter(
                (event) =>
                  since.current === null ||
                  Date.parse(event.timestamp) >= since.current,
              ),
            ),
          );
      } catch {
        // Preserve the last successful feed during reconnection.
      } finally {
        if (!controller.signal.aborted)
          timer = setTimeout(() => void poll(), 500);
      }
    };
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, []);
  return { logs, clear };
}
