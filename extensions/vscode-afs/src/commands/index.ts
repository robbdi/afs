import * as path from "path";
import * as vscode from "vscode";
import type { BinaryInfo } from "../transport/clientFactory";
import type { ITransportClient } from "../transport/types";
import type { ContextService } from "../services/contextService";
import type { FileService } from "../services/fileService";
import type { IndexService } from "../services/indexService";
import { MountType } from "../types";
import type { ContextTreeProvider } from "../views/contextTreeProvider";
import { registerAfs, unregisterAfs, checkRegistration } from "../mcp/registration";

interface CommandDeps {
  transport: ITransportClient;
  contextService: ContextService;
  fileService: FileService;
  indexService: IndexService;
  treeProvider: ContextTreeProvider;
  binaryInfo: BinaryInfo;
  logger: vscode.OutputChannel;
}

async function pickWorkspaceFolder(): Promise<vscode.WorkspaceFolder | undefined> {
  const folders = vscode.workspace.workspaceFolders ?? [];
  if (folders.length === 0) {
    vscode.window.showWarningMessage("No workspace folder is open.");
    return undefined;
  }
  if (folders.length === 1) {
    return folders[0];
  }
  const picked = await vscode.window.showQuickPick(
    folders.map((folder) => ({ label: folder.name, detail: folder.uri.fsPath, folder })),
    { placeHolder: "Select workspace folder" },
  );
  return picked?.folder;
}

export function registerCommands(
  context: vscode.ExtensionContext,
  deps: CommandDeps,
): void {
  const { transport, contextService, indexService, treeProvider, binaryInfo, logger } =
    deps;

  context.subscriptions.push(
    vscode.commands.registerCommand("afs.treeView.refresh", () => {
      treeProvider.refresh();
    }),

    vscode.commands.registerCommand("afs.context.discover", async () => {
      try {
        const contexts = await contextService.discover();
        treeProvider.refresh();
        vscode.window.showInformationMessage(`Found ${contexts.length} context(s)`);
      } catch (err) {
        vscode.window.showErrorMessage(`Discovery failed: ${err}`);
      }
    }),

    vscode.commands.registerCommand("afs.context.init", async () => {
      const folder = await pickWorkspaceFolder();
      if (!folder) return;

      const contextPath = path.join(folder.uri.fsPath, ".context");
      let force = false;
      try {
        await vscode.workspace.fs.stat(vscode.Uri.file(contextPath));
        const choice = await vscode.window.showWarningMessage(
          `.context already exists in ${folder.name}. Recreate it with --force?`,
          { modal: true },
          "Force Recreate",
          "Cancel",
        );
        if (choice !== "Force Recreate") return;
        force = true;
      } catch {
        // context does not exist yet
      }

      try {
        const result = await contextService.init(folder.uri.fsPath, { force });
        treeProvider.refresh();
        vscode.window.showInformationMessage(
          `Initialized context at ${result.context_path}`,
        );
      } catch (err) {
        vscode.window.showErrorMessage(`Context init failed: ${err}`);
      }
    }),

    vscode.commands.registerCommand("afs.context.mount", async () => {
      const folder = await pickWorkspaceFolder();
      if (!folder) return;

      const sourcePick = await vscode.window.showOpenDialog({
        canSelectFiles: true,
        canSelectFolders: true,
        canSelectMany: false,
        openLabel: "Select Source to Mount",
      });
      if (!sourcePick?.length) return;
      const sourcePath = sourcePick[0].fsPath;

      const mountType = await vscode.window.showQuickPick(Object.values(MountType), {
        placeHolder: "Select mount type",
      });
      if (!mountType) return;

      const suggestedAlias = path.basename(sourcePath);
      const aliasInput = await vscode.window.showInputBox({
        prompt: "Mount alias (optional)",
        value: suggestedAlias,
      });
      if (aliasInput === undefined) return;
      const alias = aliasInput.trim() || undefined;

      try {
        const contextPath = path.join(folder.uri.fsPath, ".context");
        const mounted = await contextService.mount(
          sourcePath,
          mountType as MountType,
          contextPath,
          alias,
        );
        treeProvider.refresh();
        vscode.window.showInformationMessage(
          `Mounted ${mounted.name} in ${mounted.mount_type}`,
        );
      } catch (err) {
        vscode.window.showErrorMessage(`Mount failed: ${err}`);
      }
    }),

    vscode.commands.registerCommand("afs.context.unmount", async () => {
      const folder = await pickWorkspaceFolder();
      if (!folder) return;

      const mountType = await vscode.window.showQuickPick(Object.values(MountType), {
        placeHolder: "Select mount type",
      });
      if (!mountType) return;

      const alias = await vscode.window.showInputBox({
        prompt: `Alias to unmount from ${mountType}`,
      });
      if (!alias?.trim()) return;

      try {
        const contextPath = path.join(folder.uri.fsPath, ".context");
        const removed = await contextService.unmount(
          mountType as MountType,
          alias.trim(),
          contextPath,
        );
        treeProvider.refresh();
        if (!removed) {
          vscode.window.showWarningMessage(
            `No mount named "${alias.trim()}" found in ${mountType}.`,
          );
          return;
        }
        vscode.window.showInformationMessage(
          `Unmounted ${alias.trim()} from ${mountType}.`,
        );
      } catch (err) {
        vscode.window.showErrorMessage(`Unmount failed: ${err}`);
      }
    }),

    vscode.commands.registerCommand("afs.index.rebuild", async () => {
      const folders = vscode.workspace.workspaceFolders;
      if (!folders?.length) return;
      const contextPath = `${folders[0].uri.fsPath}/.context`;
      try {
        await vscode.window.withProgress(
          {
            location: vscode.ProgressLocation.Notification,
            title: "Rebuilding AFS index...",
          },
          async () => {
            const summary = await indexService.rebuild(contextPath);
            vscode.window.showInformationMessage(
              `Index rebuilt: ${summary.rows_written} rows, ${summary.errors.length} errors`,
            );
          },
        );
        treeProvider.refresh();
      } catch (err) {
        vscode.window.showErrorMessage(`Index rebuild failed: ${err}`);
      }
    }),

    vscode.commands.registerCommand("afs.index.query", async () => {
      const query = await vscode.window.showInputBox({
        prompt: "Search context index",
      });
      if (!query) return;
      const folders = vscode.workspace.workspaceFolders;
      if (!folders?.length) return;
      const contextPath = `${folders[0].uri.fsPath}/.context`;
      try {
        const entries = await indexService.query(contextPath, query);
        if (entries.length === 0) {
          vscode.window.showInformationMessage("No results found.");
          return;
        }
        const picked = await vscode.window.showQuickPick(
          entries.map((e) => ({
            label: e.relative_path,
            description: `${e.mount_type} (${e.size_bytes} bytes)`,
            detail: e.absolute_path,
          })),
          { placeHolder: `${entries.length} results for "${query}"` },
        );
        if (picked?.detail) {
          const doc = await vscode.workspace.openTextDocument(
            vscode.Uri.file(picked.detail),
          );
          await vscode.window.showTextDocument(doc);
        }
      } catch (err) {
        vscode.window.showErrorMessage(`Query failed: ${err}`);
      }
    }),

    vscode.commands.registerCommand("afs.index.queryQuickOpen", async () => {
      await vscode.commands.executeCommand("afs.index.query");
    }),

    vscode.commands.registerCommand("afs.mcp.register", async () => {
      await registerAfs(binaryInfo, logger);
    }),

    vscode.commands.registerCommand("afs.mcp.unregister", async () => {
      await unregisterAfs(logger);
    }),

    vscode.commands.registerCommand("afs.mcp.status", async () => {
      const reg = checkRegistration();
      const caps = transport.capabilities();
      const lines = [
        `Connected: ${transport.isReady()}`,
        `Capabilities: tools=${caps.tools}, resources=${caps.resources}, prompts=${caps.prompts}`,
        `MCP registered: ${reg.registered}`,
        `Config path: ${reg.configPath ?? "none"}`,
      ];
      vscode.window.showInformationMessage(lines.join("\n"), { modal: true });
    }),

    vscode.commands.registerCommand("afs.server.restart", async () => {
      const choice = await vscode.window.showWarningMessage(
        "Restart AFS server by reloading the window?",
        { modal: true },
        "Reload Window",
        "Cancel",
      );
      if (choice !== "Reload Window") return;
      logger.appendLine("[cmd] Reloading window to restart AFS server");
      await vscode.commands.executeCommand("workbench.action.reloadWindow");
    }),

    vscode.commands.registerCommand("afs.server.showLogs", () => {
      logger.show(true);
    }),
  );
}
