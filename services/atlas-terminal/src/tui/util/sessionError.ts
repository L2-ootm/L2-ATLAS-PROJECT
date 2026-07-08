function normalizeError(value: unknown): unknown {
  if (value instanceof Error) {
    return {
      name: value.name,
      message: value.message,
      stack: value.stack,
    }
  }
  return value
}

export function formatSessionCreateError(error: unknown): string {
  const seen = new WeakSet<object>()
  return JSON.stringify(normalizeError(error), (_key, value) => {
    const normalized = normalizeError(value)
    if (normalized && typeof normalized === "object") {
      if (seen.has(normalized)) return "[Circular]"
      seen.add(normalized)
    }
    return normalized
  })
}

export function logSessionCreateError(error: unknown): void {
  console.error("ATLAS_SESSION_CREATE_ERROR", formatSessionCreateError(error))
}
