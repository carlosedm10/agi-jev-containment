import { Button } from "@/components/ui/button";

export function PageTabs({ page, runId }: { page: "dashboard" | "trace"; runId?: string | null }) {
  const query = runId ? `?run=${encodeURIComponent(runId)}` : "";
  return (
    <nav aria-label="Dashboard pages" className="flex gap-1 rounded-md border bg-zinc-100 p-1">
      <Button asChild size="sm" variant={page === "dashboard" ? "default" : "ghost"}>
        <a href={`/${query}`} aria-current={page === "dashboard" ? "page" : undefined}>Dashboard</a>
      </Button>
      {runId ? (
        <Button asChild size="sm" variant={page === "trace" ? "default" : "ghost"}>
          <a href={`/trace${query}`} aria-current={page === "trace" ? "page" : undefined}>View trace</a>
        </Button>
      ) : <Button size="sm" variant="ghost" disabled>View trace</Button>}
    </nav>
  );
}
