import * as vscode from "vscode";
import { DEFAULT_TIMEOUT_MS } from "../constants";
import { CliClient } from "./cliClient";
import { McpStdioClient } from "./mcpStdioClient";
import type { ITransportClient } from "./types";

export interface BinaryInfo {
  command: string;
  args: string[];
  env: Record<string, string>;
}

export async function createTransport(
  binaryInfo: BinaryInfo,
  logger: vscode.OutputChannel,
): Promise<ITransportClient> {
  const config = vscode.workspace.getConfiguration("afs");
  const mode = config.get<string>("server.mode", "auto");
  const timeout = config.get<number>("server.timeout", DEFAULT_TIMEOUT_MS);
  const extraArgs = config.get<string[]>("server.args", []);
  const extraEnv = config.get<Record<string, string>>("server.env", {});

  const env = { ...binaryInfo.env, ...extraEnv };

  if (mode === "cli") {
    return new CliClient(binaryInfo.command, binaryInfo.args, env, logger, timeout);
  }

  // MCP mode or auto
  const mcpArgs = [...binaryInfo.args, "mcp", "serve", ...extraArgs];
  const client = new McpStdioClient(binaryInfo.command, mcpArgs, env, logger, timeout);

  if (mode === "auto") {
    try {
      await client.initialize();
      return client;
    } catch (err) {
      logger.appendLine(`[info] MCP transport failed, falling back to CLI: ${err}`);
      client.dispose();
      return new CliClient(binaryInfo.command, binaryInfo.args, env, logger, timeout);
    }
  }

  return client;
}
