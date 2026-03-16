import type {
  ConnectionState,
  McpPrompt,
  McpPromptMessage,
  McpResource,
  McpResourceContent,
  ToolSpec,
} from "../../src/types";
import type { ITransportClient, ServerCapabilities } from "../../src/transport/types";

/** Minimal event emitter for tests (no vscode dependency). */
class SimpleEventEmitter<T> {
  private listeners: Array<(e: T) => void> = [];
  event = (listener: (e: T) => void) => {
    this.listeners.push(listener);
    return { dispose: () => { this.listeners = this.listeners.filter(l => l !== listener); } };
  };
  fire(data: T): void {
    for (const listener of this.listeners) listener(data);
  }
  dispose(): void {
    this.listeners = [];
  }
}

export class MockTransport implements ITransportClient {
  private ready = true;
  private _onConnectionStateChanged = new SimpleEventEmitter<ConnectionState>();
  readonly onConnectionStateChanged = this._onConnectionStateChanged.event;

  public toolResponses: Record<string, Record<string, unknown>> = {};
  public resourceList: McpResource[] = [];
  public promptList: McpPrompt[] = [];

  async initialize(): Promise<void> {
    this.ready = true;
  }

  isReady(): boolean {
    return this.ready;
  }

  capabilities(): ServerCapabilities {
    return { tools: true, resources: true, prompts: true };
  }

  async callTool(
    name: string,
    _args: Record<string, unknown>,
  ): Promise<Record<string, unknown>> {
    return this.toolResponses[name] ?? {};
  }

  async listTools(): Promise<ToolSpec[]> {
    return [];
  }

  async listResources(): Promise<McpResource[]> {
    return this.resourceList;
  }

  async readResource(uri: string): Promise<McpResourceContent> {
    return { uri, text: "{}" };
  }

  async listPrompts(): Promise<McpPrompt[]> {
    return this.promptList;
  }

  async getPrompt(_name: string): Promise<McpPromptMessage[]> {
    return [];
  }

  dispose(): void {
    this.ready = false;
    this._onConnectionStateChanged.dispose();
  }
}
