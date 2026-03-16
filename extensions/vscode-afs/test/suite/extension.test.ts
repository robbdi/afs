import * as assert from "node:assert";
import { describe, it } from "node:test";
import { MountType, PolicyType, DEFAULT_POLICIES } from "../../src/types";
import { EXTENSION_ID, MCP_PROTOCOL_VERSION } from "../../src/constants";

describe("Types", () => {
  it("MountType enum values match Python models", () => {
    assert.strictEqual(MountType.MEMORY, "memory");
    assert.strictEqual(MountType.KNOWLEDGE, "knowledge");
    assert.strictEqual(MountType.TOOLS, "tools");
    assert.strictEqual(MountType.SCRATCHPAD, "scratchpad");
    assert.strictEqual(MountType.HISTORY, "history");
    assert.strictEqual(MountType.HIVEMIND, "hivemind");
    assert.strictEqual(MountType.GLOBAL, "global");
    assert.strictEqual(MountType.ITEMS, "items");
    assert.strictEqual(MountType.MONOREPO, "monorepo");
  });

  it("PolicyType enum values match Python schema", () => {
    assert.strictEqual(PolicyType.READ_ONLY, "read_only");
    assert.strictEqual(PolicyType.WRITABLE, "writable");
    assert.strictEqual(PolicyType.EXECUTABLE, "executable");
  });

  it("DEFAULT_POLICIES covers all mount types", () => {
    const mountTypes = Object.values(MountType);
    for (const mt of mountTypes) {
      assert.ok(mt in DEFAULT_POLICIES, `Missing default policy for ${mt}`);
    }
  });

  it("DEFAULT_POLICIES match Python defaults", () => {
    assert.strictEqual(DEFAULT_POLICIES[MountType.MEMORY], PolicyType.READ_ONLY);
    assert.strictEqual(DEFAULT_POLICIES[MountType.TOOLS], PolicyType.EXECUTABLE);
    assert.strictEqual(DEFAULT_POLICIES[MountType.SCRATCHPAD], PolicyType.WRITABLE);
    assert.strictEqual(DEFAULT_POLICIES[MountType.MONOREPO], PolicyType.READ_ONLY);
  });
});

describe("Constants", () => {
  it("extension ID is defined", () => {
    assert.strictEqual(EXTENSION_ID, "afs-vscode");
  });

  it("MCP protocol version matches Python server", () => {
    assert.strictEqual(MCP_PROTOCOL_VERSION, "2024-11-05");
  });
});
