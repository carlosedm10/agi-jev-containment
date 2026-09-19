import { useEffect, useState } from "react";

import type { IncidentState } from "@/ladder/types";

const INCIDENT_URL = "/api/demo/incidents/latest";
const POLL_MS = 500;

export function useIncidentFeed(runId?: string | null): IncidentState | null {
  const [incident, setIncident] = useState<IncidentState | null>(null);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    setIncident(null);
    const poll = async () => {
      try {
        const url = runId
          ? `/api/demo/incidents/${encodeURIComponent(runId)}`
          : INCIDENT_URL;
        const res = await fetch(url, { signal: controller.signal });
        const next = res.ok ? ((await res.json()) as IncidentState) : null;
        if (active) setIncident(next);
      } catch {
        // backend offline — keep last good state
      } finally {
        if (active) timer = setTimeout(() => void poll(), POLL_MS);
      }
    };
    void poll();
    return () => {
      active = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [runId]);

  return incident;
}
