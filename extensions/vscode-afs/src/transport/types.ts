import * as vscode from "vscode";
import type {
  ConnectionState,
  McpPrompt,
  McpPromptMessage,
  McpResource,
  McpResourceContent,
  ToolSpec,
} from "../types";

export interface JsonRpcRequest {
  jsonrpc: "2.0";
  id: number | string;
  method: string;
  params?: Record<string, unknown>;
}

export interface JsonRpcResponse {
  jsonrpc: "2.0";
  id: number | string | null;
  result?: Record<string, unknown>;
  error?: { code: number; message: string };
}

export interface JsonRpcNotification {
  jsonrpc: "2.0";
  method: string;
  params?: Record<string, unknown>;
}

/** Server capabilities detected during MCP handshake. */
export interface ServerCapabilities {
  tools: boolean;
  resources: boolean;
  prompts: boolean;
}

/** Transport abstraction for communicating with AFS backend. */
export interface ITransportClient extends vscode.Disposable {
  initialize(): Promise<void>;
  isReady(): boolean;
  capabilities(): ServerCapabilities;

  // Tools
  callTool(name: string, args: Record<string, unknown>): Promise<Record<string, unknown>>;
  listTools(): Promise<ToolSpec[]>;

  // Resources
  listResources(): Promise<McpResource[]>;
  readResource(uri: string): Promise<McpResourceContent>;

  // Prompts
  listPrompts(): Promise<McpPrompt[]>;
  getPrompt(name: string, args?: Record<string, unknown>): Promise<McpPromptMessage[]>;

  onConnectionStateChanged: vscode.Event<ConnectionState>;
}
