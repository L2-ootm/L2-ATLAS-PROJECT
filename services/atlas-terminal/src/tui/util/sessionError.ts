import { appendDiagnostic } from "../../util/diagnosticLog"

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
  const detail = formatSessionCreateError(error)
  // stderr line for headless harnesses; the file for interactive runs, where
  // the fullscreen renderer overdraws console output.
  console.error("ATLAS_SESSION_CREATE_ERROR", detail)
  appendDiagnostic("ATLAS_SESSION_CREATE_ERROR", detail)
}
