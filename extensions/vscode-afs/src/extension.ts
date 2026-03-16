import * as vscode from "vscode";
import { TREE_VIEW_ID } from "./constants";
import { registerCommands } from "./commands/index";
import { ContextService } from "./services/contextService";
import { FileService } from "./services/fileService";
import { IndexService } from "./services/indexService";
import { createTransport, type BinaryInfo } from "./transport/clientFactory";
import type { ITransportClient } from "./transport/types";
import { locateAfsBinary } from "./utils/binaryLocator";
import { createLogger } from "./utils/logger";
import { ContextTreeProvider } from "./views/contextTreeProvider";
import { AfsStatusBar } from "./views/statusBar";

let client: ITransportClient | undefined;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const logger = createLogger();
  context.subscriptions.push(logger);

  const binaryInfo: BinaryInfo = locateAfsBinary(logger);

  const showEmptyMounts = vscode.workspace
    .getConfiguration("afs")
    .get<boolean>("treeView.showEmptyMounts", false);

  let transport: ITransportClient;
  try {
    transport = await createTransport(binaryInfo, logger);
    if (!transport.isReady()) {
      await transport.initialize();
    }
  } catch (err) {
    logger.appendLine(`[activate] Transport init failed: ${err}`);
    vscode.window.showWarningMessage(
      "AFS: Could not connect to backend. Some features may be limited.",
    );
    // Create CLI fallback for degraded mode
    transport = await createTransport(
      { ...binaryInfo, args: binaryInfo.args },
      logger,
    );
  }
  client = transport;
  context.subscriptions.push(transport);

  const contextService = new ContextService(transport);
  const fileService = new FileService(transport);
  const indexService = new IndexService(transport);

  const statusBar = new AfsStatusBar();
  context.subscriptions.push(statusBar);
  transport.onConnectionStateChanged((state) => statusBar.update(state));
  statusBar.update(transport.isReady() ? "connected" : "disconnected");

  const treeProvider = new ContextTreeProvider(
    contextService,
    fileService,
    showEmptyMounts,
  );
  context.subscriptions.push(
    vscode.window.registerTreeDataProvider(TREE_VIEW_ID, treeProvider),
  );

  registerCommands(context, {
    transport,
    contextService,
    fileService,
    indexService,
    treeProvider,
    binaryInfo,
    logger,
  });

  const watcher = vscode.workspace.createFileSystemWatcher(
    "**/.context/metadata.json",
  );
  watcher.onDidChange(() => treeProvider.refresh());
  watcher.onDidCreate(() => treeProvider.refresh());
  watcher.onDidDelete(() => treeProvider.refresh());
  context.subscriptions.push(watcher);

  const caps = transport.capabilities();
  vscode.commands.executeCommand("setContext", "afs.active", transport.isReady());
  vscode.commands.executeCommand("setContext", "afs.mcp.hasResources", caps.resources);
  vscode.commands.executeCommand("setContext", "afs.mcp.hasPrompts", caps.prompts);

  logger.appendLine(
    `[activate] AFS extension ready. Connected: ${transport.isReady()}, ` +
      `Capabilities: tools=${caps.tools} resources=${caps.resources} prompts=${caps.prompts}`,
  );
}

export function deactivate(): void {
  client?.dispose();
  client = undefined;
}
