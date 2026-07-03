// ATLAS shim adapted from MiMo-Code (MIT). Type/helper surface only —
// no donor server/runtime logic. See ATTRIBUTION.md.

import type z from "zod"

export interface Metadata {
	[key: string]: any
}

export interface Info<Parameters extends z.ZodType = z.ZodType, M extends Metadata = Metadata> {
	id: string
	parameters?: Parameters
	__metadata?: M
}

// Shim fidelity: tool schemas are not vendored, so rendering code sees
// loose records instead of per-tool shapes.
export type InferParameters<_T> = Record<string, any>
export type InferMetadata<_T> = Record<string, any>
