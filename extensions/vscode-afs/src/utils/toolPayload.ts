export function extractToolPayload(
  result: Record<string, unknown> | null | undefined,
): Record<string, unknown> | null {
  if (!result || typeof result !== "object") {
    return null;
  }

  const structured = Reflect.get(result, "structuredContent");
  if (structured && typeof structured === "object" && !Array.isArray(structured)) {
    return structured as Record<string, unknown>;
  }

  const content = Reflect.get(result, "content");
  if (Array.isArray(content) && content.length > 0) {
    const first = content[0];
    if (first && typeof first === "object") {
      const text = Reflect.get(first, "text");
      if (typeof text === "string" && text.trim()) {
        try {
          const parsed = JSON.parse(text);
          if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
            return parsed as Record<string, unknown>;
          }
        } catch {
          return null;
        }
      }
    }
  }

  return result;
}
