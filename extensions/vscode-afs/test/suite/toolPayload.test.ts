import * as assert from "node:assert";
import { describe, it } from "node:test";
import { extractToolPayload } from "../../src/utils/toolPayload";

describe("extractToolPayload", () => {
  it("passes through direct transport payloads", () => {
    const payload = { entries_count: 3, stale: false };
    assert.deepStrictEqual(extractToolPayload(payload), payload);
  });

  it("extracts JSON payloads from MCP content wrappers", () => {
    const payload = extractToolPayload({
      content: [{ type: "text", text: "{\"count\":2}" }],
    });

    assert.deepStrictEqual(payload, { count: 2 });
  });

  it("prefers structuredContent when present", () => {
    const payload = extractToolPayload({
      structuredContent: { count: 4 },
      content: [{ type: "text", text: "{\"count\":2}" }],
    });

    assert.deepStrictEqual(payload, { count: 4 });
  });
});
