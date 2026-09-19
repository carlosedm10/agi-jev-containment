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
  expect(
    trace.some(
      (entry) =>
        entry.label.includes("Queued") && entry.meta.includes("stage=0"),
    ),
  ).toBe(true);
  incident.actions = [{ ...incident.actions[0], name: "contain_agent", mode: "simulated", ladder_level: 3 }];
  const containment = actionsFromIncident(incident)[0];
  expect(containment.title).toBe("Pause the agent and revoke its proxy token");
  expect(containment.details.some((entry) => entry.label === "Mode")).toBe(false);
  expect(containment.details.find((entry) => entry.label === "Reference commands")?.meta).toContain("docker pause");
  expect(containment.details.find((entry) => entry.label === "Execution")?.meta).toContain("not executed");
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
