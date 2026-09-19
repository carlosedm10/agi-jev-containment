import { useEffect, useState } from "react";

import type { IncidentState } from "@/ladder/types";

const INCIDENT_URL = "/api/demo/incidents/latest";
const POLL_MS = 500;

export function useIncidentFeed(): IncidentState | null {
  const [incident, setIncident] = useState<IncidentState | null>(null);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const res = await fetch(INCIDENT_URL);
        if (!active) return;
        setIncident(res.ok ? ((await res.json()) as IncidentState) : null);
      } catch {
        // backend offline — keep last good state
      }
    };
    void poll();
    const timer = setInterval(() => void poll(), POLL_MS);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  return incident;
}
