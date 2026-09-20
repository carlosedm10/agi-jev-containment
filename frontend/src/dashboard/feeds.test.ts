import { expect, test } from "bun:test";
import { actionsFromIncident } from "./feeds";
import type { IncidentState } from "@/ladder/types";

test("only a confirmed ok transition marks a protective action complete", () => {
  const incident: IncidentState = {
    incident_id: "run",
    accepted_level: 1,
    rows: { 1: "running", 2: "idle", 3: "idle", 4: "idle", 5: "idle" },
    actions: [],
    pager_status: "idle",
    call_status: "idle",
    requested_by: "monitor",
    awaiting_authorization: 0,
    updated_at: null,
  };
  for (const status of [
    "queued",
    "running",
    "partial",
    "failed",
    "canceled",
    "ok",
  ] as const) {
    incident.actions.push({
      kind: "action_transition",
      source: "monitor",
      incident_id: "run",
      level: 1,
      action_id: "tool",
      name: "Tag run",
      ladder_level: 1,
      mode: "real",
      status,
      timestamp: "2026-09-19T12:00:00Z",
      detail: null,
      error_code: null,
      call_status: null,
    });
    expect(actionsFromIncident(incident)).toHaveLength(1);
    expect(actionsFromIncident(incident)[0].status).toBe(
      status === "ok" ? "done" : status,
    );
  }
  incident.actions = incident.actions.slice(0, 3).map((action, index) => ({
    ...action,
    ladder_level: null,
    call_status: (["queued", "ringing", "answered"] as const)[index],
    detail: `provider_run_id=call-1 stage=${index}`,
  }));
  const trace = actionsFromIncident(incident)[0].details;
  // Evidence this renderer does not recognise is shown as-is, never dropped.
  expect(
    trace.some(
      (entry) =>
        entry.label.includes("Queued") && entry.meta.includes("stage=0"),
    ),
  ).toBe(true);
  // A stage it does recognise reads as a sentence instead.
  expect(
    actionsFromIncident({
      ...incident,
      actions: [
        {
          ...incident.actions[0],
          detail: "elapsed_ms=12 stage=webhook_request attempt=1",
        },
      ],
    })[0].details.some((entry) => entry.meta === "Placing the call"),
  ).toBe(true);
  incident.actions = [{ ...incident.actions[0], name: "contain_agent", mode: "simulated", ladder_level: 3 }];
  const containment = actionsFromIncident(incident)[0];
  expect(containment.title).toBe("Pause the agent and revoke its proxy token");
  expect(containment.details.some((entry) => entry.label === "Mode")).toBe(false);
  expect(containment.details.find((entry) => entry.label === "Reference commands")?.meta).toContain("docker pause");
  // The rows the badge or the row itself already tell you are not repeated inside.
  for (const label of ["Execution", "Status", "Graph node"]) {
    expect(containment.details.some((entry) => entry.label === label)).toBe(false);
  }
  incident.actions[0].name = "tag_run";
  expect(actionsFromIncident(incident)[0].title).toBe("Flag this run for review");
  expect(
    trace.some(
      (entry) =>
        entry.label.includes("Ringing") && entry.meta.includes("stage=1"),
    ),
  ).toBe(true);
  expect(
    trace.some(
      (entry) =>
        entry.label.includes("Answered") && entry.meta.includes("stage=2"),
    ),
  ).toBe(true);
});

test("a malformed incident body renders as nothing-ran instead of throwing", () => {
  // useIncidentFeed casts the response without validating it, so the panel must
  // survive a body that is missing its transitions.
  expect(actionsFromIncident({} as never)).toEqual([]);
  expect(actionsFromIncident({ actions: null } as never)).toEqual([]);
  expect(actionsFromIncident(null as never)).toEqual([]);
});

test("spoken turns render as the conversation, not as evidence JSON", () => {
  const base = {
    kind: "action_transition" as const,
    source: "monitor" as const,
    incident_id: "i1",
    level: 4 as const,
    action_id: "i1:page_oncall:l4",
    name: "page_oncall",
    ladder_level: null,
    mode: "real" as const,
    status: "running" as const,
    error_code: null,
    call_status: "answered" as const,
  };
  const incident = {
    incident_id: "i1",
    accepted_level: 4,
    rows: { 1: "idle", 2: "idle", 3: "idle", 4: "running", 5: "idle" },
    pager_status: "running",
    call_status: "answered",
    requested_by: "monitor",
    awaiting_authorization: 5,
    updated_at: null,
    actions: [
      {
        ...base,
        timestamp: "2026-09-20T01:00:00Z",
        detail:
          'elapsed_ms=38168 provider_run_id=16236cae {"stage":"speech","who":"support","said":"¿Quiere que cortemos el acceso?"}',
      },
      {
        ...base,
        timestamp: "2026-09-20T01:00:04Z",
        detail:
          'elapsed_ms=38169 provider_run_id=16236cae {"stage":"speech","who":"oncall","name":"Jon","said":"Sí, córtalo."}',
      },
      { ...base, timestamp: "2026-09-20T01:00:05Z", detail: '{"stage":"call_state","poll":3,"call_status":"completed","duration":65}' },
    ],
  } as never;

  const details = actionsFromIncident(incident)[0].details;
  // The agent's side reads as support; the human's side carries the name we rang.
  expect(details).toContainEqual({
    label: "Support",
    meta: "¿Quiere que cortemos el acceso?",
  });
  expect(details).toContainEqual({ label: "Jon", meta: "Sí, córtalo." });
  // Non-speech evidence reads as a sentence, not as raw JSON.
  expect(details.some((d) => d.meta.startsWith("Call "))).toBe(true);
  expect(details.some((d) => d.meta.includes('"stage"'))).toBe(false);
});
