import { describe, expect, test } from "bun:test"
import { readFileSync } from "node:fs"
import { appendDiagnostic, diagnosticLogPath } from "../src/util/diagnosticLog"

describe("diagnosticLog", () => {
	test("appendDiagnostic persists a tagged line to the well-known file", () => {
		const marker = `marker-${Date.now()}-${Math.random().toString(36).slice(2)}`
		appendDiagnostic("ATLAS_TEST_DIAG", marker)
		const content = readFileSync(diagnosticLogPath(), "utf8")
		expect(content).toContain(`ATLAS_TEST_DIAG ${marker}`)
	})
})
