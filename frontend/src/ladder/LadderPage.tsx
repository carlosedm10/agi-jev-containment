import { useEffect, useMemo, useState } from "react";

import { ActionLadder } from "./ActionLadder";
import { ACTION_STATUS_LABEL } from "./copy";
import { toLadderState } from "./state";
import type { IncidentState } from "./types";
import { actionModeLabel, newestActions } from "./wallboard";
import "./ladder.css";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const LATEST_INCIDENT_URL = `${API_BASE_URL}/api/demo/incidents/latest`;
const REQUEST_TIMEOUT_MS = 5_000;

export function LadderPage() {
  const [incident, setIncident] = useState<IncidentState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let controller: AbortController | null = null;

    async function poll() {
      if (controller) return;
      const requestController = new AbortController();
      controller = requestController;
      let timedOut = false;
      const timeout = window.setTimeout(() => {
        timedOut = true;
        requestController.abort();
      }, REQUEST_TIMEOUT_MS);

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

        const nextIncident = (await response.json()) as IncidentState;
        if (!active || requestController.signal.aborted) return;
        setIncident(nextIncident);
        setError(null);
      } catch (cause) {
        if (!active || (requestController.signal.aborted && !timedOut)) return;
        setError(
          timedOut
            ? "Feed request timed out"
            : cause instanceof Error
              ? cause.message
              : "Feed request failed",
        );
      } finally {
        window.clearTimeout(timeout);
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
  const timelineActions = useMemo(
    () => (incident ? newestActions(incident.actions) : []),
    [incident],
  );

  const kill = ladderState?.level === 5;

  return (
    <div className={`ladder-page ${kill ? "is-kill" : ""}`}>
      <main className="app">
        <header className="wallboard-header">
          <div>
            <h1>{kill ? "Pull the plug" : "Hack Spain"}</h1>
            <span className="feed-label">
              {kill ? "Kill path" : "Live ladder"}
            </span>
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
              {timelineActions.length ? (
                <ol>
                  {timelineActions.map((action, index) => (
                    <li key={`${action.action_id}:${action.timestamp}:${index}`}>
                      <div className="action-heading">
                        <strong>{action.name}</strong>
                        <span className={`action-status is-${action.status}`}>
                          {ACTION_STATUS_LABEL[action.status]}
                        </span>
                      </div>
                      <p className="action-meta">
                        {actionModeLabel(action.mode)} ·{" "}
                        {formatUpdatedAt(action.timestamp)}
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
            <p>Waiting for an incident.</p>
          </section>
        )}
      </main>
    </div>
  );
}

function formatUpdatedAt(timestamp: string | null): string {
  if (!timestamp) return "Waiting for first transition";
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? timestamp : date.toLocaleTimeString();
}
