import { useEffect, useMemo, useState } from "react";

import { ActionLadder } from "./ladder/ActionLadder";
import { toLadderState } from "./ladder/state";
import type { IncidentState } from "./ladder/types";
import "./App.css";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const LATEST_INCIDENT_URL = `${API_BASE_URL}/api/demo/incidents/latest`;

export default function App() {
  const [incident, setIncident] = useState<IncidentState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let controller: AbortController | null = null;

    async function poll() {
      if (controller) return;
      const requestController = new AbortController();
      controller = requestController;

      try {
        const response = await fetch(LATEST_INCIDENT_URL, {
          signal: requestController.signal,
        });
        if (!active) return;

        if (response.status === 404) {
          setIncident(null);
          setError(null);
          return;
        }
        if (!response.ok) {
          throw new Error(`Feed request failed (${response.status})`);
        }

        setIncident((await response.json()) as IncidentState);
        setError(null);
      } catch (cause) {
        if (!active || requestController.signal.aborted) return;
        setError(
          cause instanceof Error ? cause.message : "Feed request failed",
        );
      } finally {
        if (controller === requestController) controller = null;
      }
    }

    void poll();
    const timer = window.setInterval(() => void poll(), 500);

    return () => {
      active = false;
      window.clearInterval(timer);
      controller?.abort();
      controller = null;
    };
  }, []);

  const ladderState = useMemo(
    () => (incident ? toLadderState(incident) : null),
    [incident],
  );

  return (
    <main className="app">
      <header className="wallboard-header">
        <div>
          <h1>hackspain</h1>
          <span className="feed-label">SIMULATED FEED</span>
        </div>
        {incident ? (
          <dl className="incident-meta">
            <div>
              <dt>Incident</dt>
              <dd>{incident.incident_id}</dd>
            </div>
            <div>
              <dt>Updated</dt>
              <dd>{formatUpdatedAt(incident.updated_at)}</dd>
            </div>
          </dl>
        ) : null}
      </header>

      {error ? (
        <p className="feed-error" role="status">
          {error}
          {incident ? " · showing last good state" : ""}
        </p>
      ) : null}

      {incident && ladderState ? (
        <>
          <ActionLadder state={ladderState} />
          <section className="timeline" aria-labelledby="timeline-heading">
            <h2 id="timeline-heading">Action timeline</h2>
            {incident.actions.length ? (
              <ol>
                {incident.actions.map((action, index) => (
                  <li key={`${action.action_id}:${action.timestamp}:${index}`}>
                    <div className="action-heading">
                      <strong>{action.name}</strong>
                      <span className={`action-status is-${action.status}`}>
                        {action.status}
                      </span>
                    </div>
                    <p className="action-meta">
                      {action.mode} · {formatUpdatedAt(action.timestamp)}
                    </p>
                    {action.detail ? <p>{action.detail}</p> : null}
                    {action.error_code ? (
                      <p className="action-error">{action.error_code}</p>
                    ) : null}
                  </li>
                ))}
              </ol>
            ) : (
              <p className="empty-actions">No action transitions yet.</p>
            )}
          </section>
        </>
      ) : (
        <section className="waiting" aria-live="polite">
          <p>Waiting for a simulated incident…</p>
        </section>
      )}
    </main>
  );
}

function formatUpdatedAt(timestamp: string | null): string {
  if (!timestamp) return "Waiting for first transition";
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? timestamp : date.toLocaleTimeString();
}
