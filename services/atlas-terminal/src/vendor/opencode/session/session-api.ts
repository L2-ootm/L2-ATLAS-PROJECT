// ATLAS shim adapted from ATLAS (MIT). Type/helper surface only —
// no donor server/runtime logic. See ATTRIBUTION.md.

/** Donor default titles look like "<prefix>2026-07-03T12:00:00.000Z". */
export function isDefaultTitle(title: string): boolean {
	return /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(title) || title === "New session"
}
