import { ChildProcess, spawn } from "child_process";
import * as vscode from "vscode";
import { MCP_PROTOCOL_VERSION } from "../constants";
import type {
  ConnectionState,
  McpPrompt,
  McpPromptMessage,
  McpResource,
  McpResourceContent,
  ToolSpec,
} from "../types";
import type { ITransportClient, JsonRpcResponse, ServerCapabilities } from "./types";

interface PendingRequest {
  resolve: (value: JsonRpcResponse) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

export class McpStdioClient implements ITransportClient {
  private process: ChildProcess | null = null;
  private nextId = 1;
  private pending = new Map<number, PendingRequest>();
  private buffer = Buffer.alloc(0);
  private ready = false;
  private caps: ServerCapabilities = { tools: false, resources: false, prompts: false };

  private readonly _onConnectionStateChanged = new vscode.EventEmitter<ConnectionState>();
  readonly onConnectionStateChanged = this._onConnectionStateChanged.event;

  constructor(
    private readonly command: string,
    private readonly args: string[],
    private readonly env: Record<string, string>,
    private readonly logger: vscode.OutputChannel,
    private readonly timeout: number = 30_000,
  ) {}

  async initialize(): Promise<void> {
    this.process = spawn(this.command, this.args, {
      stdio: ["pipe", "pipe", "pipe"],
      env: { ...process.env, ...this.env },
    });

    this.process.stdout!.on("data", (chunk: Buffer) => this.onData(chunk));
    this.process.stderr!.on("data", (chunk: Buffer) => {
      this.logger.appendLine(`[stderr] ${chunk.toString("utf-8").trimEnd()}`);
    });
    this.process.on("exit", (code) => {
      this.ready = false;
      this.rejectAll(new Error(`AFS server exited with code ${code}`));
      this._onConnectionStateChanged.fire("disconnected");
    });
    this.process.on("error", (err) => {
      this.ready = false;
      this.rejectAll(err);
      this._onConnectionStateChanged.fire("error");
    });

    // MCP handshake
    const initResult = await this.sendRequest("initialize", {
      protocolVersion: MCP_PROTOCOL_VERSION,
      capabilities: {},
      clientInfo: { name: "afs-vscode", version: "0.1.0" },
    });

    const serverCaps = (initResult.result as Record<string, unknown>)?.capabilities;
    if (serverCaps && typeof serverCaps === "object") {
      const capsObj = serverCaps as Record<string, unknown>;
      this.caps = {
        tools: !!capsObj.tools,
        resources: !!capsObj.resources,
        prompts: !!capsObj.prompts,
      };
    }

    // Send initialized notification (no response expected)
    this.sendNotification("notifications/initialized", {});

    this.ready = true;
    this._onConnectionStateChanged.fire("connected");
  }

  isReady(): boolean {
    return this.ready;
  }

  capabilities(): ServerCapabilities {
    return { ...this.caps };
  }

  async callTool(name: string, args: Record<string, unknown>): Promise<Record<string, unknown>> {
    const resp = await this.sendRequest("tools/call", { name, arguments: args });
    if (resp.error) {
      throw new Error(resp.error.message);
    }
    const result = resp.result ?? {};
    // Extract structuredContent if present (AFS wraps tool results)
    if ("structuredContent" in result && typeof result.structuredContent === "object") {
      return result.structuredContent as Record<string, unknown>;
    }
    return result;
  }

  async listTools(): Promise<ToolSpec[]> {
    const resp = await this.sendRequest("tools/list", {});
    if (resp.error) throw new Error(resp.error.message);
    return ((resp.result as Record<string, unknown>)?.tools ?? []) as ToolSpec[];
  }

  async listResources(): Promise<McpResource[]> {
    if (!this.caps.resources) return [];
    const resp = await this.sendRequest("resources/list", {});
    if (resp.error) throw new Error(resp.error.message);
    return ((resp.result as Record<string, unknown>)?.resources ?? []) as McpResource[];
  }

  async readResource(uri: string): Promise<McpResourceContent> {
    if (!this.caps.resources) throw new Error("Server does not support resources");
    const resp = await this.sendRequest("resources/read", { uri });
    if (resp.error) throw new Error(resp.error.message);
    const contents = (resp.result as Record<string, unknown>)?.contents;
    if (Array.isArray(contents) && contents.length > 0) {
      return contents[0] as McpResourceContent;
    }
    return { uri };
  }

  async listPrompts(): Promise<McpPrompt[]> {
    if (!this.caps.prompts) return [];
    const resp = await this.sendRequest("prompts/list", {});
    if (resp.error) throw new Error(resp.error.message);
    return ((resp.result as Record<string, unknown>)?.prompts ?? []) as McpPrompt[];
  }

  async getPrompt(name: string, args?: Record<string, unknown>): Promise<McpPromptMessage[]> {
    if (!this.caps.prompts) throw new Error("Server does not support prompts");
    const resp = await this.sendRequest("prompts/get", { name, arguments: args ?? {} });
    if (resp.error) throw new Error(resp.error.message);
    return ((resp.result as Record<string, unknown>)?.messages ?? []) as McpPromptMessage[];
  }

  dispose(): void {
    this.rejectAll(new Error("Client disposed"));
    if (this.process) {
      this.process.kill();
      this.process = null;
    }
    this.ready = false;
    this._onConnectionStateChanged.dispose();
  }

  // --- Private ---

  private sendRequest(method: string, params: Record<string, unknown>): Promise<JsonRpcResponse> {
    return new Promise((resolve, reject) => {
      if (!this.process?.stdin?.writable) {
        return reject(new Error("Transport not connected"));
      }
      const id = this.nextId++;
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Request ${method} (id=${id}) timed out after ${this.timeout}ms`));
      }, this.timeout);

      this.pending.set(id, { resolve, reject, timer });
      this.writeMessage({ jsonrpc: "2.0", id, method, params });
    });
  }

  private sendNotification(method: string, params: Record<string, unknown>): void {
    if (!this.process?.stdin?.writable) return;
    this.writeMessage({ jsonrpc: "2.0", method, params });
  }

  private writeMessage(payload: Record<string, unknown>): void {
    const body = Buffer.from(JSON.stringify(payload), "utf-8");
    const header = Buffer.from(`Content-Length: ${body.length}\r\n\r\n`, "ascii");
    this.process!.stdin!.write(header);
    this.process!.stdin!.write(body);
  }

  private onData(chunk: Buffer): void {
    this.buffer = Buffer.concat([this.buffer, chunk]);
    while (this.tryParseMessage()) {
      // keep parsing
    }
  }

  private tryParseMessage(): boolean {
    const headerEnd = this.buffer.indexOf("\r\n\r\n");
    if (headerEnd === -1) return false;

    const headerStr = this.buffer.subarray(0, headerEnd).toString("ascii");
    const match = /content-length:\s*(\d+)/i.exec(headerStr);
    if (!match) {
      // Discard malformed header
      this.buffer = this.buffer.subarray(headerEnd + 4);
      return true;
    }

    const contentLength = parseInt(match[1], 10);
    const bodyStart = headerEnd + 4;
    if (this.buffer.length < bodyStart + contentLength) return false;

    const bodyBuf = this.buffer.subarray(bodyStart, bodyStart + contentLength);
    this.buffer = this.buffer.subarray(bodyStart + contentLength);

    try {
      const msg = JSON.parse(bodyBuf.toString("utf-8")) as JsonRpcResponse;
      this.handleResponse(msg);
    } catch {
      this.logger.appendLine("[warn] Failed to parse MCP message");
    }
    return true;
  }

  private handleResponse(msg: JsonRpcResponse): void {
    if (msg.id == null) return; // notification, ignore
    const id = typeof msg.id === "string" ? parseInt(msg.id, 10) : msg.id;
    const pending = this.pending.get(id);
    if (!pending) return;
    this.pending.delete(id);
    clearTimeout(pending.timer);
    pending.resolve(msg);
  }

  private rejectAll(err: Error): void {
    for (const [id, pending] of this.pending) {
      clearTimeout(pending.timer);
      pending.reject(err);
      this.pending.delete(id);
    }
  }
}
