// ATLAS shim — donor external-plugin/server machinery is intentionally
// disabled (no second runtime). Typed loosely; see ATTRIBUTION.md.

export const Instance: any = {
	provide: async (opts: any) => (typeof opts?.fn === "function" ? opts.fn() : undefined),
}
