// ATLAS shim adapted from ATLAS (MIT). Type/helper surface only —
// no donor server/runtime logic. See ATTRIBUTION.md.

import z from "zod"

export const FileDiff = z.object({
	file: z.string(),
	patch: z.string(),
	additions: z.number(),
	deletions: z.number(),
	status: z.enum(["added", "deleted", "modified"]).optional(),
})
export type FileDiff = z.infer<typeof FileDiff>
