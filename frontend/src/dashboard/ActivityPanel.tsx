import { Diamond } from "@/components/loading-ui/diamond";
import TaskRows from "@/components/ui/task-rows";
import type { SafeAction } from "@/dashboard/demo";
import { localTime } from "@/lib/time";

export function ActivityPanel({
  actions,
  selectedNodeId,
  onSelectNode,
  title = "Protective actions",
  empty = "Waiting for Jev",
}: {
  actions: SafeAction[];
  selectedNodeId: string | null;
  onSelectNode: (id: string) => void;
  title?: string;
  empty?: string;
}) {
  return (
    <section
      aria-label={title}
      className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-md border bg-[#fcfcfc] shadow-xs"
    >
      <header className="flex h-10 shrink-0 items-center border-b border-[#b06a38] bg-[#d59566] px-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-[#1a1614]">
          {title}
        </h2>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {actions.length > 0 ? (
          <TaskRows
            variant="List"
            rows={actions.map((action) => ({
              key: action.id,
              label: action.title,
              amount: `${action.source} · L${action.level} · ${localTime(action.startedAt)}`,
              status: action.status,
              selected: action.nodeId === selectedNodeId,
              details: action.details,
            }))}
            onToggleRow={(id, open) => {
              const action = actions.find((entry) => entry.id === id);
              if (open && action) onSelectNode(action.nodeId);
            }}
          />
        ) : (
          <div className="grid place-content-center px-4 py-14">
            {/* The label carries the meaning; the pixels carry the waiting. */}
            <Diamond aria-label={empty} className="size-8 text-[#b06a38]" />
          </div>
        )}
      </div>
    </section>
  );
}
