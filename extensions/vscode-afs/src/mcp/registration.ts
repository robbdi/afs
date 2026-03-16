import { existsSync, readFileSync, writeFileSync, copyFileSync, mkdirSync } from "fs";
import * as path from "path";
import * as vscode from "vscode";
import type { BinaryInfo } from "../transport/clientFactory";

interface McpServersConfig {
  mcpServers?: Record<string, { command: string; args?: string[] }>;
}

/** Detect likely MCP config file path for the current editor. */
export function detectMcpConfigPath(): string | null {
  const override = vscode.workspace
    .getConfiguration("afs")
    .get<string>("mcp.configPath", "")
    .trim();
  if (override) return override;

  const home = process.env.HOME ?? process.env.USERPROFILE ?? "";
  if (!home) return null;

  const candidates: string[] = [];

  // Workspace-level configs first
  for (const folder of vscode.workspace.workspaceFolders ?? []) {
    candidates.push(path.join(folder.uri.fsPath, ".cursor", "mcp.json"));
  }

  // User-level configs
  candidates.push(
    path.join(home, ".cursor", "mcp.json"),
    path.join(home, ".config", "cursor", "mcp.json"),
    path.join(
      home,
      "Library",
      "Application Support",
      "Claude",
      "claude_desktop_config.json",
    ),
  );

  for (const candidate of candidates) {
    if (existsSync(candidate)) return candidate;
  }

  // Default: workspace .cursor/mcp.json (will be created)
  const firstFolder = vscode.workspace.workspaceFolders?.[0];
  if (firstFolder) {
    return path.join(firstFolder.uri.fsPath, ".cursor", "mcp.json");
  }

  return null;
}

function buildServerEntry(
  binaryInfo: BinaryInfo,
): { command: string; args: string[] } {
  return {
    command: binaryInfo.command,
    args: [...binaryInfo.args, "mcp", "serve"],
  };
}

/** Register AFS in the editor's MCP config with preview and backup. */
export async function registerAfs(
  binaryInfo: BinaryInfo,
  logger: vscode.OutputChannel,
): Promise<boolean> {
  const configPath = detectMcpConfigPath();
  if (!configPath) {
    vscode.window.showErrorMessage(
      "Could not determine MCP config path. Set afs.mcp.configPath in settings.",
    );
    return false;
  }

  let existing: McpServersConfig = {};
  if (existsSync(configPath)) {
    try {
      existing = JSON.parse(readFileSync(configPath, "utf-8"));
    } catch {
      existing = {};
    }
  }

  const entry = buildServerEntry(binaryInfo);
  const newConfig = {
    ...existing,
    mcpServers: {
      ...(existing.mcpServers ?? {}),
      afs: entry,
    },
  };

  const preview = JSON.stringify(newConfig, null, 2);
  const choice = await vscode.window.showInformationMessage(
    `Register AFS MCP server in ${configPath}?`,
    { modal: true, detail: preview },
    "Register",
    "Cancel",
  );

  if (choice !== "Register") return false;

  // Backup existing file
  if (existsSync(configPath)) {
    const backupPath = `${configPath}.${Date.now()}.backup`;
    copyFileSync(configPath, backupPath);
    logger.appendLine(`[mcp] Backed up ${configPath} -> ${backupPath}`);
  }

  const dir = path.dirname(configPath);
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }

  writeFileSync(configPath, JSON.stringify(newConfig, null, 2), "utf-8");
  logger.appendLine(`[mcp] Registered AFS in ${configPath}`);
  vscode.window.showInformationMessage(`AFS registered in ${configPath}`);
  return true;
}

/** Unregister AFS from the editor's MCP config. */
export async function unregisterAfs(
  logger: vscode.OutputChannel,
): Promise<boolean> {
  const configPath = detectMcpConfigPath();
  if (!configPath || !existsSync(configPath)) {
    vscode.window.showInformationMessage("No MCP config found to unregister from.");
    return false;
  }

  let config: McpServersConfig;
  try {
    config = JSON.parse(readFileSync(configPath, "utf-8"));
  } catch {
    vscode.window.showErrorMessage("Could not parse MCP config.");
    return false;
  }

  if (!config.mcpServers?.afs) {
    vscode.window.showInformationMessage("AFS is not registered in MCP config.");
    return false;
  }

  const choice = await vscode.window.showWarningMessage(
    `Remove AFS from ${configPath}?`,
    { modal: true },
    "Remove",
    "Cancel",
  );

  if (choice !== "Remove") return false;

  const backupPath = `${configPath}.${Date.now()}.backup`;
  copyFileSync(configPath, backupPath);
  logger.appendLine(`[mcp] Backed up ${configPath} -> ${backupPath}`);

  delete config.mcpServers.afs;
  writeFileSync(configPath, JSON.stringify(config, null, 2), "utf-8");
  logger.appendLine(`[mcp] Unregistered AFS from ${configPath}`);
  vscode.window.showInformationMessage(`AFS removed from ${configPath}`);
  return true;
}

/** Check registration status. */
export function checkRegistration(): {
  registered: boolean;
  configPath: string | null;
} {
  const configPath = detectMcpConfigPath();
  if (!configPath || !existsSync(configPath)) {
    return { registered: false, configPath };
  }
  try {
    const config: McpServersConfig = JSON.parse(readFileSync(configPath, "utf-8"));
    return { registered: !!config.mcpServers?.afs, configPath };
  } catch {
    return { registered: false, configPath };
  }
}
