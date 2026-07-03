// ATLAS shim adapted from MiMo-Code (MIT). Type/helper surface only —
// no donor server/runtime logic. See ATTRIBUTION.md.

export const GO_UPSELL_MESSAGE = "__donor_go_upsell__" // never emitted by ATLAS

export function isRateLimitMessage(message: string): boolean {
	const lower = message.toLowerCase()
	return (
		lower.includes("too many requests") ||
		lower.includes("rate limit") ||
		lower.includes("rate increased too quickly")
	)
}
