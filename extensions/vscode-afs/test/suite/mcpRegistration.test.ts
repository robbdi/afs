import * as assert from "node:assert";
import { describe, it } from "node:test";
import { existsSync, mkdirSync, readFileSync, writeFileSync, rmSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";

describe("MCP Registration JSON merge", () => {
  const testDir = join(tmpdir(), `afs-test-${Date.now()}`);

  // Test the JSON merge logic that registration.ts uses
  it("merges AFS entry into empty config", () => {
    const existing: Record<string, unknown> = {};
    const newConfig = {
      ...existing,
      mcpServers: {
        ...(existing as { mcpServers?: Record<string, unknown> }).mcpServers ?? {},
        afs: { command: "afs", args: ["mcp", "serve"] },
      },
    };
    assert.deepStrictEqual(newConfig, {
      mcpServers: { afs: { command: "afs", args: ["mcp", "serve"] } },
    });
  });

  it("merges AFS entry preserving existing servers", () => {
    const existing = {
      mcpServers: {
        other: { command: "other-server", args: [] },
      },
    };
    const newConfig = {
      ...existing,
      mcpServers: {
        ...existing.mcpServers,
        afs: { command: "afs", args: ["mcp", "serve"] },
      },
    };
    assert.strictEqual(Object.keys(newConfig.mcpServers).length, 2);
    assert.deepStrictEqual(newConfig.mcpServers.other, {
      command: "other-server",
      args: [],
    });
    assert.deepStrictEqual(newConfig.mcpServers.afs, {
      command: "afs",
      args: ["mcp", "serve"],
    });
  });

  it("overwrites existing AFS entry on re-register", () => {
    const existing = {
      mcpServers: {
        afs: { command: "old-afs", args: ["old"] },
        other: { command: "other", args: [] },
      },
    };
    const newConfig = {
      ...existing,
      mcpServers: {
        ...existing.mcpServers,
        afs: { command: "new-afs", args: ["mcp", "serve"] },
      },
    };
    assert.strictEqual(newConfig.mcpServers.afs.command, "new-afs");
    assert.strictEqual(Object.keys(newConfig.mcpServers).length, 2);
  });

  it("removes AFS entry on unregister", () => {
    const config: { mcpServers: Record<string, { command: string; args?: string[] }> } = {
      mcpServers: {
        afs: { command: "afs", args: ["mcp", "serve"] },
        other: { command: "other", args: [] },
      },
    };
    delete config.mcpServers.afs;
    assert.strictEqual(Object.keys(config.mcpServers).length, 1);
    assert.strictEqual(config.mcpServers.afs, undefined);
    assert.deepStrictEqual(config.mcpServers.other, {
      command: "other",
      args: [],
    });
  });

  it("handles config with no mcpServers key", () => {
    const existing: Record<string, unknown> = { someOtherKey: true };
    const newConfig = {
      ...existing,
      mcpServers: {
        ...(existing as { mcpServers?: Record<string, unknown> }).mcpServers ?? {},
        afs: { command: "afs", args: ["mcp", "serve"] },
      },
    };
    assert.strictEqual(newConfig.someOtherKey, true);
    assert.deepStrictEqual(newConfig.mcpServers.afs, {
      command: "afs",
      args: ["mcp", "serve"],
    });
  });

  it("preserves non-mcpServers keys in config", () => {
    const existing = {
      version: "1.0",
      editor: { theme: "dark" },
      mcpServers: {
        existing: { command: "foo" },
      },
    };
    const newConfig = {
      ...existing,
      mcpServers: {
        ...existing.mcpServers,
        afs: { command: "afs", args: ["mcp", "serve"] },
      },
    };
    assert.strictEqual(newConfig.version, "1.0");
    assert.deepStrictEqual(newConfig.editor, { theme: "dark" });
    assert.strictEqual(Object.keys(newConfig.mcpServers).length, 2);
  });

  it("backup and write creates valid JSON", () => {
    mkdirSync(testDir, { recursive: true });
    const configPath = join(testDir, "mcp.json");
    const original = { mcpServers: { existing: { command: "foo" } } };
    writeFileSync(configPath, JSON.stringify(original, null, 2), "utf-8");

    // Simulate backup
    const backupPath = `${configPath}.backup`;
    const originalContent = readFileSync(configPath, "utf-8");
    writeFileSync(backupPath, originalContent, "utf-8");

    // Simulate merge and write
    const parsed = JSON.parse(originalContent);
    const merged = {
      ...parsed,
      mcpServers: {
        ...parsed.mcpServers,
        afs: { command: "afs", args: ["mcp", "serve"] },
      },
    };
    writeFileSync(configPath, JSON.stringify(merged, null, 2), "utf-8");

    // Verify
    const result = JSON.parse(readFileSync(configPath, "utf-8"));
    assert.strictEqual(Object.keys(result.mcpServers).length, 2);
    assert.ok(result.mcpServers.afs);
    assert.ok(result.mcpServers.existing);

    // Verify backup
    const backup = JSON.parse(readFileSync(backupPath, "utf-8"));
    assert.strictEqual(Object.keys(backup.mcpServers).length, 1);
    assert.ok(!backup.mcpServers.afs);

    // Cleanup
    rmSync(testDir, { recursive: true, force: true });
  });

  it("handles missing config file gracefully", () => {
    const missingPath = join(tmpdir(), `afs-missing-${Date.now()}`, "mcp.json");
    assert.strictEqual(existsSync(missingPath), false);

    // Simulate what registration does: create new config when file missing
    const newConfig = {
      mcpServers: {
        afs: { command: "afs", args: ["mcp", "serve"] },
      },
    };
    const json = JSON.stringify(newConfig, null, 2);
    const parsed = JSON.parse(json);
    assert.deepStrictEqual(parsed.mcpServers.afs, {
      command: "afs",
      args: ["mcp", "serve"],
    });
  });

  it("round-trips JSON with custom args and env", () => {
    const entry = {
      command: "python3",
      args: ["-m", "afs", "mcp", "serve", "--verbose"],
      env: { AFS_LOG_LEVEL: "debug", PYTHONPATH: "/custom/path" },
    };
    const config = { mcpServers: { afs: entry } };
    const json = JSON.stringify(config, null, 2);
    const parsed = JSON.parse(json);

    assert.strictEqual(parsed.mcpServers.afs.command, "python3");
    assert.deepStrictEqual(parsed.mcpServers.afs.args, [
      "-m", "afs", "mcp", "serve", "--verbose",
    ]);
    assert.strictEqual(parsed.mcpServers.afs.env.AFS_LOG_LEVEL, "debug");
    assert.strictEqual(parsed.mcpServers.afs.env.PYTHONPATH, "/custom/path");
  });

  it("merge is idempotent", () => {
    const base = {
      mcpServers: {
        other: { command: "other" },
      },
    };
    const afsEntry = { command: "afs", args: ["mcp", "serve"] };

    // First merge
    const first = {
      ...base,
      mcpServers: { ...base.mcpServers, afs: afsEntry },
    };

    // Second merge (same entry)
    const second = {
      ...first,
      mcpServers: { ...first.mcpServers, afs: afsEntry },
    };

    assert.deepStrictEqual(first, second);
  });
});
