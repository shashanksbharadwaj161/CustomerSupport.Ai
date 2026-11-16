export type ServerMsg = { type: "shaon"; event: string; [k: string]: any };
export type TransportKind = "smallwebrtc" | "websocket";
export interface CallClient {
  kind: TransportKind;
  connect(): Promise<void>;
  disconnect(): void;
  send(msg: Record<string, unknown>): void;
  onMessage: (m: ServerMsg) => void;
  onClose: (reason: string) => void;
  micNode(): { ctx: AudioContext; node: AudioNode } | null;
  outNode(): { ctx: AudioContext; node: AudioNode } | null;
}
