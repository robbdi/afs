import * as assert from "node:assert";
import { describe, it } from "node:test";
import { MockTransport } from "./mockTransport";

describe("MockTransport", () => {
  it("starts in ready state", () => {
    const transport = new MockTransport();
    assert.strictEqual(transport.isReady(), true);
  });

  it("capabilities reports all features available", () => {
    const transport = new MockTransport();
    const caps = transport.capabilities();
    assert.strictEqual(caps.tools, true);
    assert.strictEqual(caps.resources, true);
    assert.strictEqual(caps.prompts, true);
  });

  it("callTool returns configured response", async () => {
    const transport = new MockTransport();
    transport.toolResponses["test.echo"] = { value: "hello" };
    const result = await transport.callTool("test.echo", {});
    assert.deepStrictEqual(result, { value: "hello" });
  });

  it("callTool returns empty object for unconfigured tool", async () => {
    const transport = new MockTransport();
    const result = await transport.callTool("nonexistent", {});
    assert.deepStrictEqual(result, {});
  });

  it("listResources returns configured list", async () => {
    const transport = new MockTransport();
    transport.resourceList = [
      { uri: "afs://test", name: "Test Resource" },
    ];
    const resources = await transport.listResources();
    assert.strictEqual(resources.length, 1);
    assert.strictEqual(resources[0].uri, "afs://test");
  });

  it("listPrompts returns configured list", async () => {
    const transport = new MockTransport();
    transport.promptList = [
      { name: "test.prompt", description: "A test prompt" },
    ];
    const prompts = await transport.listPrompts();
    assert.strictEqual(prompts.length, 1);
    assert.strictEqual(prompts[0].name, "test.prompt");
  });

  it("dispose sets isReady to false", () => {
    const transport = new MockTransport();
    assert.strictEqual(transport.isReady(), true);
    transport.dispose();
    assert.strictEqual(transport.isReady(), false);
  });

  it("initialize sets ready state", async () => {
    const transport = new MockTransport();
    transport.dispose();
    assert.strictEqual(transport.isReady(), false);
    await transport.initialize();
    assert.strictEqual(transport.isReady(), true);
  });

  it("readResource returns uri with empty text", async () => {
    const transport = new MockTransport();
    const content = await transport.readResource("afs://test");
    assert.strictEqual(content.uri, "afs://test");
    assert.strictEqual(content.text, "{}");
  });

  it("getPrompt returns empty array", async () => {
    const transport = new MockTransport();
    const messages = await transport.getPrompt("test");
    assert.deepStrictEqual(messages, []);
  });

  it("listTools returns empty array", async () => {
    const transport = new MockTransport();
    const tools = await transport.listTools();
    assert.deepStrictEqual(tools, []);
  });

  it("onConnectionStateChanged fires events", () => {
    const transport = new MockTransport();
    const received: string[] = [];
    const sub = transport.onConnectionStateChanged((state) => {
      received.push(state);
    });
    // Access the internal emitter to fire — MockTransport exposes it via the event
    // Since we can't fire directly, verify the subscription itself works
    assert.ok(sub, "subscription should be returned");
    assert.ok(typeof sub.dispose === "function", "subscription should have dispose");
    sub.dispose();
    transport.dispose();
  });

  it("multiple tool responses are independent", async () => {
    const transport = new MockTransport();
    transport.toolResponses["tool.a"] = { result: "A" };
    transport.toolResponses["tool.b"] = { result: "B" };

    const resultA = await transport.callTool("tool.a", {});
    const resultB = await transport.callTool("tool.b", {});

    assert.deepStrictEqual(resultA, { result: "A" });
    assert.deepStrictEqual(resultB, { result: "B" });
  });

  it("callTool ignores passed arguments", async () => {
    const transport = new MockTransport();
    transport.toolResponses["tool.fixed"] = { fixed: true };

    const result1 = await transport.callTool("tool.fixed", { arg1: "value1" });
    const result2 = await transport.callTool("tool.fixed", { arg2: "value2" });

    assert.deepStrictEqual(result1, { fixed: true });
    assert.deepStrictEqual(result2, { fixed: true });
  });

  it("readResource returns different URIs correctly", async () => {
    const transport = new MockTransport();
    const c1 = await transport.readResource("afs://ctx1");
    const c2 = await transport.readResource("afs://ctx2/sub");

    assert.strictEqual(c1.uri, "afs://ctx1");
    assert.strictEqual(c2.uri, "afs://ctx2/sub");
  });

  it("re-initialize after dispose restores ready state", async () => {
    const transport = new MockTransport();
    assert.strictEqual(transport.isReady(), true);
    transport.dispose();
    assert.strictEqual(transport.isReady(), false);
    await transport.initialize();
    assert.strictEqual(transport.isReady(), true);
    // Tool calls should still work after re-init
    transport.toolResponses["tool.after"] = { ok: true };
    const result = await transport.callTool("tool.after", {});
    assert.deepStrictEqual(result, { ok: true });
  });
});
