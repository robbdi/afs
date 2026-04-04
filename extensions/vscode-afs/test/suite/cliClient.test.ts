import * as assert from "node:assert";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { describe, it } from "node:test";
import { workspace } from "vscode";
import { CliClient } from "../../src/transport/cliClient";

function writeFakeAfsBinary(tmpDir: string, logPath: string): string {
  const scriptPath = path.join(tmpDir, "fake-afs.js");
  fs.writeFileSync(
    scriptPath,
    `#!/usr/bin/env node
const fs = require("node:fs");
const path = require("node:path");
const args = process.argv.slice(2);
const logPath = process.env.CLI_TEST_LOG;
const root = process.env.CLI_TEST_ROOT;
const promptJson = path.join(root, "session_system_prompt_vscode.json");
const promptText = path.join(root, "session_system_prompt_vscode.txt");
const payloadJson = path.join(root, "session_client_vscode.json");

fs.appendFileSync(
  logPath,
  JSON.stringify({
    args,
    env: {
      AFS_SESSION_ID: process.env.AFS_SESSION_ID || "",
      AFS_SESSION_CLIENT_PAYLOAD_JSON: process.env.AFS_SESSION_CLIENT_PAYLOAD_JSON || "",
      AFS_SESSION_SYSTEM_PROMPT_JSON: process.env.AFS_SESSION_SYSTEM_PROMPT_JSON || "",
      AFS_SESSION_SYSTEM_PROMPT_TEXT: process.env.AFS_SESSION_SYSTEM_PROMPT_TEXT || "",
      AFS_ACTIVE_CONTEXT_ROOT: process.env.AFS_ACTIVE_CONTEXT_ROOT || "",
    },
  }) + "\\n",
);

if (args.length === 1 && args[0] === "--help") {
  process.stdout.write("help");
  process.exit(0);
}

if (args[0] === "session" && args[1] === "prepare-client") {
  fs.writeFileSync(promptText, "You are the VS Code AFS harness.\\n", "utf-8");
  fs.writeFileSync(
    promptJson,
    JSON.stringify({ text: "You are the VS Code AFS harness." }, null, 2),
    "utf-8",
  );
  fs.writeFileSync(payloadJson, "{}", "utf-8");
  process.stdout.write(
    JSON.stringify({
      client: "vscode",
      session_id: "sess-test",
      context_path: path.join(root, "workspace", ".context"),
      prompt: {
        artifact_paths: {
          json: promptJson,
          text: promptText,
        },
      },
      artifact_paths: {
        json: payloadJson,
      },
    }),
  );
  process.exit(0);
}

if (args[0] === "session" && (args[1] === "hook" || args[1] === "event")) {
  process.stdout.write("{}");
  process.exit(0);
}

if (args[0] === "fs" && args[1] === "read") {
  if (args[3] === "missing.txt") {
    process.stderr.write("missing file");
    process.exit(1);
  }
  process.stdout.write("from-context");
  process.exit(0);
}

process.stderr.write("unsupported command: " + args.join(" "));
process.exit(1);
`,
    "utf-8",
  );
  fs.chmodSync(scriptPath, 0o755);
  return scriptPath;
}

function readLogEntries(logPath: string): Array<{ args: string[]; env: Record<string, string> }> {
  const raw = fs.readFileSync(logPath, "utf-8").trim();
  if (!raw) {
    return [];
  }
  return raw.split("\n").map((line) => JSON.parse(line));
}

describe("CliClient", () => {
  it("prepares a VS Code session harness and exports prompt artifacts to tool calls", async () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "afs-cli-client-"));
    const logPath = path.join(tmpDir, "cli.log");
    const workspaceRoot = path.join(tmpDir, "workspace");
    const notePath = path.join(workspaceRoot, ".context", "scratchpad", "note.md");
    fs.mkdirSync(path.dirname(notePath), { recursive: true });
    fs.writeFileSync(notePath, "", "utf-8");
    workspace.workspaceFolders = [{ uri: { fsPath: workspaceRoot } }];

    const client = new CliClient(
      writeFakeAfsBinary(tmpDir, logPath),
      [],
      {
        CLI_TEST_LOG: logPath,
        CLI_TEST_ROOT: tmpDir,
      },
      {
        appendLine() {},
        dispose() {},
      } as never,
      5_000,
    );

    await client.initialize();
    const result = await client.callTool("context.read", { path: notePath });
    assert.deepStrictEqual(result, { path: notePath, content: "from-context" });
    client.dispose();
    await new Promise((resolve) => setTimeout(resolve, 50));

    const calls = readLogEntries(logPath);
    assert.ok(calls.some((entry) => entry.args[0] === "session" && entry.args[1] === "prepare-client"));
    assert.ok(calls.some((entry) => entry.args[0] === "session" && entry.args[1] === "hook" && entry.args[2] === "session_start"));
    assert.ok(calls.some((entry) => entry.args[0] === "session" && entry.args[1] === "event" && entry.args[2] === "task_created"));
    assert.ok(calls.some((entry) => entry.args[0] === "session" && entry.args[1] === "event" && entry.args[2] === "task_completed"));
    assert.ok(calls.some((entry) => entry.args[0] === "session" && entry.args[1] === "hook" && entry.args[2] === "session_end"));

    const fsReadCall = calls.find((entry) => entry.args[0] === "fs" && entry.args[1] === "read");
    assert.ok(fsReadCall);
    assert.strictEqual(fsReadCall.env.AFS_SESSION_ID.length, 12);
    assert.strictEqual(fsReadCall.env.AFS_SESSION_CLIENT_PAYLOAD_JSON, path.join(tmpDir, "session_client_vscode.json"));
    assert.strictEqual(fsReadCall.env.AFS_SESSION_SYSTEM_PROMPT_JSON, path.join(tmpDir, "session_system_prompt_vscode.json"));
    assert.strictEqual(fsReadCall.env.AFS_SESSION_SYSTEM_PROMPT_TEXT, path.join(tmpDir, "session_system_prompt_vscode.txt"));
    assert.strictEqual(fsReadCall.env.AFS_ACTIVE_CONTEXT_ROOT, path.join(tmpDir, "workspace", ".context"));
  });

  it("emits task_failed when the CLI command errors", async () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "afs-cli-client-fail-"));
    const logPath = path.join(tmpDir, "cli.log");
    const workspaceRoot = path.join(tmpDir, "workspace");
    const missingPath = path.join(workspaceRoot, ".context", "scratchpad", "missing.txt");
    fs.mkdirSync(path.dirname(missingPath), { recursive: true });
    workspace.workspaceFolders = [{ uri: { fsPath: workspaceRoot } }];

    const client = new CliClient(
      writeFakeAfsBinary(tmpDir, logPath),
      [],
      {
        CLI_TEST_LOG: logPath,
        CLI_TEST_ROOT: tmpDir,
      },
      {
        appendLine() {},
        dispose() {},
      } as never,
      5_000,
    );

    await client.initialize();
    await assert.rejects(() => client.callTool("context.read", { path: missingPath }));
    client.dispose();
    await new Promise((resolve) => setTimeout(resolve, 50));

    const calls = readLogEntries(logPath);
    assert.ok(calls.some((entry) => entry.args[0] === "session" && entry.args[1] === "event" && entry.args[2] === "task_failed"));
  });
});
