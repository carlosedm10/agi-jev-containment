import { expect, test } from "bun:test";
import { actionToolName, PROTECTIVE_TOOLS } from "./tools";

test("recovers the tool name from journalled action ids", () => {
  expect(actionToolName("trigger-ab12:contain_agent")).toBe("contain_agent");
  expect(actionToolName("trigger-ab12:page_oncall:l5")).toBe("page_oncall");
  // A run id containing a colon must not shift which segment is read as the tool.
  expect(actionToolName("weird:run:id:kill_agent_swarm")).toBe("kill_agent_swarm");
  expect(actionToolName(null)).toBeNull();
  expect(actionToolName("trigger-ab12:notify_sms")).toBeNull();
});

test("the catalog holds exactly the tools the dispatcher can run", () => {
  // Mirrors ActionService._plan. Anything else is a tool this system does not have.
  expect(Object.keys(PROTECTIVE_TOOLS).sort()).toEqual([
    "contain_agent",
    "copy_forensics",
    "cut_environment_egress",
    "kill_agent_swarm",
    "page_oncall",
    "tag_run",
  ]);
});
