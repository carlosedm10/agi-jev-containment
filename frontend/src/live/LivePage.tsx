import { useDemo } from "@/dashboard/demo";
import { useGraphStream } from "@/graph/useGraphStream";
import { LiveGraph } from "@/live/LiveGraph";

function StreamSource() {
  const { graph, status } = useGraphStream();
  return <LiveGraph graph={graph} status={status} />;
}

function DemoSource() {
  const { graph } = useDemo();
  return <LiveGraph graph={graph} status="live" />;
}

export function LivePage({ demo }: { demo: boolean }) {
  return demo ? <DemoSource /> : <StreamSource />;
}
