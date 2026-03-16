import { execFileSync } from "child_process";
import { existsSync } from "fs";
import * as path from "path";
import * as vscode from "vscode";
import type { BinaryInfo } from "../transport/clientFactory";

/** Locate the AFS binary following the same resolution as scripts/afs. */
export function locateAfsBinary(logger: vscode.OutputChannel): BinaryInfo {
  const config = vscode.workspace.getConfiguration("afs");

  // 1. Explicit command setting
  const explicitCommand = config.get<string>("server.command", "").trim();
  if (explicitCommand) {
    logger.appendLine(`[binary] Using explicit command: ${explicitCommand}`);
    return { command: explicitCommand, args: [], env: {} };
  }

  // 2. Explicit Python path → run as module
  const pythonPath = config.get<string>("server.pythonPath", "").trim();
  if (pythonPath) {
    logger.appendLine(`[binary] Using explicit Python: ${pythonPath}`);
    return { command: pythonPath, args: ["-m", "afs"], env: {} };
  }

  const workspaceFolders = vscode.workspace.workspaceFolders ?? [];

  for (const folder of workspaceFolders) {
    const root = folder.uri.fsPath;

    // 3. Workspace .venv/bin/python with afs installed
    const venvPython = path.join(root, ".venv", "bin", "python");
    if (existsSync(venvPython)) {
      logger.appendLine(`[binary] Found workspace venv: ${venvPython}`);
      return { command: venvPython, args: ["-m", "afs"], env: {} };
    }

    // 4. Workspace scripts/afs (dev mode)
    const scriptsAfs = path.join(root, "scripts", "afs");
    if (existsSync(scriptsAfs)) {
      logger.appendLine(`[binary] Found workspace scripts/afs: ${scriptsAfs}`);
      return {
        command: scriptsAfs,
        args: [],
        env: { AFS_ROOT: root, PYTHONPATH: path.join(root, "src") },
      };
    }
  }

  // 5. afs on PATH
  try {
    execFileSync("afs", ["--help"], { timeout: 5000, stdio: "ignore" });
    logger.appendLine("[binary] Found afs on PATH");
    return { command: "afs", args: [], env: {} };
  } catch {
    // not found
  }

  // 6. system python3 -m afs
  try {
    execFileSync("python3", ["-m", "afs", "--help"], { timeout: 5000, stdio: "ignore" });
    logger.appendLine("[binary] Using system python3 -m afs");
    return { command: "python3", args: ["-m", "afs"], env: {} };
  } catch {
    // not found
  }

  logger.appendLine("[binary] No AFS binary found — extension will run in degraded mode");
  return { command: "afs", args: [], env: {} };
}
