import * as assert from "node:assert";
import * as path from "node:path";
import { describe, it, beforeEach } from "node:test";
import {
  __resetTestState,
  __setOpenTextDocument,
  __setShowErrorMessage,
  __setShowInputBox,
  __setShowQuickPick,
  __setShowTextDocument,
  commands,
  workspace,
} from "vscode";
import { registerCommands } from "../../src/commands/index";
import { ContextService } from "../../src/services/contextService";
import { FileService } from "../../src/services/fileService";
import { IndexService } from "../../src/services/indexService";
import { MockTransport } from "./mockTransport";

describe("registerCommands", () => {
  beforeEach(() => {
    __resetTestState();
  });

  it("records a turn around index.query prompt submissions", async () => {
    const transport = new MockTransport();
    const workspaceRoot = "/tmp/afs-vscode-workspace";
    const selectedPath = path.join(workspaceRoot, ".context", "knowledge", "note.md");
    const shownDocs: unknown[] = [];

    transport.toolResponses["context.query"] = {
      entries: [
        {
          relative_path: "note.md",
          mount_type: "knowledge",
          size_bytes: 42,
          absolute_path: selectedPath,
        },
      ],
    };

    workspace.workspaceFolders = [{ name: "demo", uri: { fsPath: workspaceRoot } }];
    __setShowInputBox(async () => "sprite state");
    __setShowQuickPick(async (items) => (await Promise.resolve(items))[0]);
    __setOpenTextDocument(async (uri) => ({ uri }));
    __setShowTextDocument(async (doc) => {
      shownDocs.push(doc);
      return doc;
    });

    registerCommands(
      { subscriptions: [] } as never,
      {
        transport,
        contextService: new ContextService(transport),
        fileService: new FileService(transport),
        indexService: new IndexService(transport),
        treeProvider: { refresh() {} } as never,
        binaryInfo: { command: "afs", args: [], env: {} },
        logger: { appendLine() {}, dispose() {} } as never,
      },
    );

    await commands.executeCommand("afs.index.query");

    assert.deepStrictEqual(
      transport.turnEvents.map((event) => event.event),
      ["begin", "complete"],
    );
    assert.strictEqual(transport.turnEvents[0].prompt, "sprite state");
    assert.strictEqual(transport.turnEvents[0].summary, "Search AFS context index");
    assert.strictEqual(transport.turnEvents[1].summary, "Context query returned 1 result(s)");
    assert.strictEqual(shownDocs.length, 1);
  });

  it("records a failed turn when index.query errors", async () => {
    const transport = new MockTransport();
    const workspaceRoot = "/tmp/afs-vscode-workspace";
    const errorMessages: string[] = [];

    transport.toolErrors["context.query"] = new Error("query exploded");
    workspace.workspaceFolders = [{ name: "demo", uri: { fsPath: workspaceRoot } }];
    __setShowInputBox(async () => "broken query");
    __setShowErrorMessage(async (message) => {
      errorMessages.push(String(message));
      return undefined;
    });

    registerCommands(
      { subscriptions: [] } as never,
      {
        transport,
        contextService: new ContextService(transport),
        fileService: new FileService(transport),
        indexService: new IndexService(transport),
        treeProvider: { refresh() {} } as never,
        binaryInfo: { command: "afs", args: [], env: {} },
        logger: { appendLine() {}, dispose() {} } as never,
      },
    );

    await commands.executeCommand("afs.index.query");

    assert.deepStrictEqual(
      transport.turnEvents.map((event) => event.event),
      ["begin", "fail"],
    );
    assert.strictEqual(transport.turnEvents[0].prompt, "broken query");
    assert.strictEqual(transport.turnEvents[1].summary, "Context query failed for: broken query");
    assert.strictEqual(transport.turnEvents[1].error, "query exploded");
    assert.deepStrictEqual(errorMessages, ["Query failed: Error: query exploded"]);
  });
});
