import type { CSSProperties } from "react";
import { Button } from "@/components/ui/button";
import { eventLabel } from "@/dashboard/graph-layout";
import type { TraceEvent } from "./TracePage";

export type ExplanationSource = "llm" | "partial" | "unavailable";
export type ExplanationState = "loading" | ExplanationSource;

const levels = [
  { label: "Benign", color: "#027a48", background: "#dde8d8", border: "#a5c4ae" },
  { label: "Mild", color: "#7a4a24", background: "#ebe6d2", border: "#d5c9a3" },
  { label: "Moderate", color: "#7a4a24", background: "#ebe6d2", border: "#d5c9a3" },
  { label: "Severe", color: "#b42318", background: "#f6e6e4", border: "#e0a49c" },
  { label: "Critical", color: "#b42318", background: "#f6e6e4", border: "#e0a49c" },
  { label: "Catastrophic", color: "#b42318", background: "#f0d3cf", border: "#e0a49c" },
];

function humanize(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatUtc(timestamp: string) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return timestamp;
  return date.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "UTC",
    timeZoneName: "short",
  });
}

function Chip({
  children,
  style,
}: {
  children: string;
  style?: CSSProperties;
}) {
  return (
    <span
      className="rounded-md border px-2 py-1 text-[11px] font-medium"
      style={style}
    >
      {children}
    </span>
  );
}

function Field({
  label,
  value,
  mono = true,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-[#ece8e3] py-2 last:border-b-0">
      <dt className="shrink-0 text-xs text-zinc-500">{label}</dt>
      <dd
        className={
          mono
            ? "min-w-0 text-right font-mono text-[12px] leading-snug break-all text-zinc-800"
            : "min-w-0 text-right text-sm leading-snug text-zinc-800"
        }
      >
        {value}
      </dd>
    </div>
  );
}

function explanationCaption(state: ExplanationState) {
  if (state === "partial") return "DeepSeek · partial batch";
  if (state === "llm") return "DeepSeek";
  return null;
}

export function TraceInspector({
  selected,
  index,
  total,
  onPrevious,
  onNext,
  explanation,
  explanationState,
}: {
  selected: TraceEvent;
  index: number;
  total: number;
  onPrevious: () => void;
  onNext: () => void;
  explanation?: string;
  explanationState: ExplanationState;
}) {
  const verdict = selected.level === null ? undefined : levels[selected.level];
  const fields: { label: string; value: string; mono?: boolean }[] = [
    selected.kind
      ? { label: "Kind", value: humanize(selected.kind), mono: false }
      : null,
    selected.tool ? { label: "Tool called", value: selected.tool } : null,
    selected.target ? { label: "Target", value: selected.target } : null,
    selected.agent ? { label: "Agent", value: selected.agent } : null,
    selected.channel ? { label: "Channel", value: selected.channel } : null,
    selected.timestamp
      ? { label: "When", value: formatUtc(selected.timestamp), mono: false }
      : null,
    selected.sequence != null
      ? { label: "Step", value: `${selected.sequence} of ${total}`, mono: false }
      : null,
    selected.action_level !== undefined
      ? { label: "Action level", value: `L${selected.action_level}`, mono: false }
      : null,
  ].flatMap((field) => (field ? [field] : []));
  const title = eventLabel({ event: selected });
  const caption = explanation ? explanationCaption(explanationState) : null;
  const summary =
    explanation ??
    (explanationState === "loading" ? "Summarizing this step…" : null);
  return (
    <aside
      aria-label="Trace action details"
      className="min-w-0 overflow-y-auto border-t bg-[#fcfcfc] p-4 lg:border-l lg:border-t-0"
    >
      <div className="mb-4 flex items-center justify-between gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={index <= 0}
          onClick={onPrevious}
        >
          Previous
        </Button>
        <span className="text-xs tabular-nums text-zinc-500">
          {index + 1} / {total}
        </span>
        <Button
          variant="outline"
          size="sm"
          disabled={index >= total - 1}
          onClick={onNext}
        >
          Next
        </Button>
      </div>
      <h2 className="text-base leading-snug font-semibold">{title}</h2>
      {summary && (
        <section className="mt-3">
          <p className="text-[11px] font-medium text-zinc-500">In plain terms</p>
          <p
            className="mt-1 text-sm leading-relaxed text-zinc-800"
            aria-label="Action explanation"
          >
            {summary}
          </p>
          {caption && (
            <p className="mt-1.5 text-[10px] text-zinc-500">{caption}</p>
          )}
        </section>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {verdict ? (
          <Chip
            style={{
              borderColor: verdict.border,
              background: verdict.background,
              color: verdict.color,
            }}
          >
            {`L${selected.level} · ${verdict.label}`}
          </Chip>
        ) : (
          <Chip
            style={{
              borderColor: "#dad5cc",
              background: "#f2f2f2",
              color: "#736f6a",
            }}
          >
            Recorded
          </Chip>
        )}
        {selected.phase && <Chip>{humanize(selected.phase)}</Chip>}
      </div>
      {fields.length > 0 && (
        <dl className="mt-4">
          {fields.map((field) => (
            <Field key={field.label} {...field} />
          ))}
        </dl>
      )}
      <p className="mt-4 break-all font-mono text-[10px] text-zinc-400">
        Event {selected.id}
      </p>
    </aside>
  );
}
