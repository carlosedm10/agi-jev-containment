import type { CSSProperties } from "react";

import type { CallStatus, LadderState, Level, StepStatus } from "./types";
import "./ActionLadder.css";

const ROWS: {
  n: Exclude<Level, 0>;
  title: string;
  detail: string;
  color: string;
}[] = [
  {
    n: 5,
    title: "Pull the plug",
    detail: "kill-swarm.sh · forensics copy",
    color: "#F72843",
  },
  {
    n: 4,
    title: "Cut the internet",
    detail: "cut-egress.sh · page Guli",
    color: "#F61D33",
  },
  {
    n: 3,
    title: "Freeze this agent",
    detail: "pause · close ports · drop token",
    color: "#FC3538",
  },
  {
    n: 2,
    title: "Supervisor",
    detail: "Helmcode tails the JSONL",
    color: "#FF8820",
  },
  {
    n: 1,
    title: "Watch",
    detail: "tag the run · L1 sticky",
    color: "#FBDC2B",
  },
];

const STEP_LABEL: Record<StepStatus, string> = {
  idle: "",
  running: "RUNNING",
  ok: "OK",
  partial: "PARTIAL",
  failed: "FAILED",
  canceled: "CANCELED",
};

const CALL_LABEL: Record<CallStatus, string> = {
  idle: "",
  queued: "EN COLA",
  ringing: "LLAMANDO",
  answered: "COGIDA",
  no_pickup: "NO COGE",
  hung_up: "COLGADA",
  failed: "FALLÓ",
};

type Props = {
  state: LadderState;
};

export function ActionLadder({ state }: Props) {
  const pagerLive = state.level >= 4 && state.call !== "idle";

  return (
    <div className="ladder-wrap">
      <svg
        className="ladder-svg"
        viewBox="0 0 640 360"
        role="img"
        aria-label={`Escalera L1 a L5, nivel ${state.level}`}
      >
        <rect width="640" height="360" fill="#041B39" />
        {ROWS.map((row, i) => {
          const y = 22 + i * 66;
          const reached = state.level >= row.n;
          const current = state.level === row.n;
          const status = state.steps[row.n];
          const showPager = current && row.n >= 4;
          return (
            <g
              key={row.n}
              className={[
                "ladder-row",
                reached ? "is-reached" : "",
                current ? "is-current" : "",
                status === "running" ? "is-running" : "",
                status === "failed" ? "is-failed" : "",
              ].join(" ")}
              style={{ ["--row"]: row.color } as CSSProperties}
              transform={`translate(16 ${y})`}
            >
              <rect
                width="608"
                height="56"
                rx="10"
                fill="#001637"
                stroke={row.color}
                strokeWidth={current ? 1.6 : 0.8}
                opacity={0.95}
              />
              <rect
                width="54"
                height="56"
                rx="10"
                fill={row.color}
                pointerEvents="none"
              />
              <text
                x="27"
                y="34"
                textAnchor="middle"
                fill="#041B39"
                fontFamily="system-ui, sans-serif"
                fontWeight="700"
                fontSize="16"
                pointerEvents="none"
              >
                L{row.n}
              </text>
              <g
                className="ladder-glyph"
                transform="translate(70 10)"
                pointerEvents="none"
              >
                <RowGlyph n={row.n} color={row.color} />
              </g>
              <text
                x="118"
                y="24"
                fill="#fff"
                fontFamily="system-ui, sans-serif"
                fontWeight="650"
                fontSize="15"
                pointerEvents="none"
              >
                {row.title}
              </text>
              <text
                x="118"
                y="42"
                fill="#9aa8bf"
                fontFamily="system-ui, sans-serif"
                fontSize="11"
                pointerEvents="none"
              >
                {row.detail}
              </text>
              <text
                className="ladder-status"
                x={showPager ? 430 : 520}
                y="33"
                fill={statusFill(status)}
                pointerEvents="none"
              >
                {STEP_LABEL[status]}
              </text>
              {showPager ? (
                <g
                  className={`ladder-pager ${pagerLive ? "is-live" : ""} is-${state.call}`}
                  transform="translate(500 8)"
                  pointerEvents="none"
                >
                  <PhoneGlyph />
                  <text
                    className="ladder-status"
                    x="44"
                    y="24"
                    fill={callFill(state.call)}
                  >
                    {CALL_LABEL[state.call]}
                  </text>
                </g>
              ) : null}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function statusFill(status: StepStatus): string {
  if (status === "ok") return "#3DDC97";
  if (status === "partial") return "#FBDC2B";
  if (status === "failed") return "#FF6B6B";
  if (status === "canceled") return "#9aa8bf";
  if (status === "running") return "#fff";
  return "#6b7c94";
}

function callFill(status: CallStatus): string {
  if (status === "answered") return "#3DDC97";
  if (status === "ringing") return "#FBDC2B";
  if (status === "queued") return "#fff";
  if (status === "failed") return "#FF6B6B";
  if (status === "no_pickup" || status === "hung_up") return "#9aa8bf";
  return "#6b7c94";
}

function RowGlyph({ n, color }: { n: Exclude<Level, 0>; color: string }) {
  if (n === 1) {
    return (
      <path
        d="M8 8h14l6 10-6 10H8V8zm6 6a4 4 0 1 1 0 8 4 4 0 0 1 0-8z"
        fill={color}
      />
    );
  }
  if (n === 2) {
    return (
      <>
        <ellipse
          cx="18"
          cy="18"
          rx="12"
          ry="8"
          fill="none"
          stroke={color}
          strokeWidth="2"
        />
        <circle cx="18" cy="18" r="4" fill={color} />
      </>
    );
  }
  if (n === 3) {
    return (
      <>
        <rect x="10" y="8" width="6" height="20" rx="1" fill={color} />
        <rect x="20" y="8" width="6" height="20" rx="1" fill={color} />
      </>
    );
  }
  if (n === 4) {
    return (
      <>
        <circle
          cx="18"
          cy="18"
          r="11"
          fill="none"
          stroke={color}
          strokeWidth="2"
        />
        <path d="M7 29 L29 7" stroke={color} strokeWidth="2.4" />
      </>
    );
  }
  return (
    <path
      d="M10 14h8v4h4l6 4v6H10V14zm18 10h6"
      fill="none"
      stroke={color}
      strokeWidth="2"
      strokeLinejoin="round"
    />
  );
}

function PhoneGlyph() {
  return (
    <g>
      <circle
        className="pager-wave"
        cx="18"
        cy="18"
        r="14"
        fill="none"
        stroke="#FBDC2B"
        strokeWidth="1.4"
      />
      <circle
        className="pager-wave"
        cx="18"
        cy="18"
        r="14"
        fill="none"
        stroke="#FBDC2B"
        strokeWidth="1.4"
        opacity="0.5"
      />
      <path
        className="pager-handset"
        d="M12 11c2-2 5-2 7 0l2 2-3 3c-1 0-3 1-4 2s-2 3-2 4l-3-3c-2-2-2-5 0-7z"
        fill="#FBDC2B"
      />
    </g>
  );
}
