import type { CSSProperties } from "react";

import { callRailLevel, CALL_LABEL, ROWS, STEP_LABEL } from "./copy";
import { LevelIcon, RingingPhone } from "./LevelIcons";
import type { LadderState } from "./types";
import "./ActionLadder.css";

const KILLSWITCH_SRC = "/killswitch-icon.animated.svg";

type Props = {
  state: LadderState;
};

export function ActionLadder({ state }: Props) {
  const kill = state.level >= 5;
  const rail = callRailLevel(state.level);

  return (
    <ol
      className={`rungs ${kill ? "is-kill" : ""}`}
      aria-label={`L1 to L5 ladder, level ${state.level}`}
    >
      {ROWS.map((row) => {
        const reached = state.level >= row.n;
        const current = state.level === row.n;
        const status = state.steps[row.n];
        const showCall = rail === row.n && state.call !== "idle";
        return (
          <li
            key={row.n}
            className={[
              "rung",
              `rung-l${row.n}`,
              reached ? "is-reached" : "",
              current ? "is-current" : "",
              status === "running" ? "is-running" : "",
              status === "failed" ? "is-failed" : "",
              showCall ? "has-call" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            style={{ ["--row"]: row.color } as CSSProperties}
          >
            <div className="rung-main">
              <span className="rung-index">L{row.n}</span>
              <span className={`rung-icon ${row.n === 5 && kill ? "is-killswitch" : ""}`}>
                {row.n === 5 && kill ? (
                  <img
                    className="killswitch"
                    src={KILLSWITCH_SRC}
                    alt=""
                    width={80}
                    height={80}
                  />
                ) : (
                  <LevelIcon n={row.n} color={row.color} />
                )}
              </span>
              <div className="rung-copy">
                <h3>{row.title}</h3>
                <p>{row.detail}</p>
              </div>
              <span className={`rung-status is-${status}`}>
                {STEP_LABEL[status]}
              </span>
            </div>
            {showCall ? (
              <aside
                className={`rung-call is-${state.call}`}
                aria-label={`On-call ${CALL_LABEL[state.call]}`}
              >
                <RingingPhone />
                <span>{CALL_LABEL[state.call]}</span>
              </aside>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
