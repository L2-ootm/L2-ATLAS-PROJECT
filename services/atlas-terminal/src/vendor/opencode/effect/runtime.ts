// ATLAS shim — donor external-plugin/server machinery is intentionally
// disabled (no second runtime). Typed loosely; see ATTRIBUTION.md.

/** Donor wraps effects into a managed runtime; ATLAS runs plain promises. */
export const makeRuntime: any = () => ({
	runPromise: async (eff: any) => eff,
	dispose: async () => undefined,
})
