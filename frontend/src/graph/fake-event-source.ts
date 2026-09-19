type Listener = (event: Event) => void;

export class FakeEventSource {
  static instances: FakeEventSource[] = [];

  readonly url: string;
  closed = false;
  private readonly listeners = new Map<string, Listener[]>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  static get last(): FakeEventSource {
    const source = FakeEventSource.instances.at(-1);
    if (source === undefined) throw new Error("no EventSource was opened");
    return source;
  }

  static reset(): void {
    FakeEventSource.instances = [];
  }

  addEventListener(type: string, listener: Listener): void {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  close(): void {
    this.closed = true;
  }

  emit(type: string, data: unknown): void {
    const payload = typeof data === "string" ? data : JSON.stringify(data);
    for (const listener of this.listeners.get(type) ?? []) {
      listener(new MessageEvent(type, { data: payload }));
    }
  }

  fail(): void {
    for (const listener of this.listeners.get("error") ?? []) {
      listener(new Event("error"));
    }
  }
}
