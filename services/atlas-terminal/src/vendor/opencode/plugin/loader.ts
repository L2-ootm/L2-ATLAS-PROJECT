// ATLAS shim — donor external-plugin/server machinery is intentionally
// disabled (no second runtime). Typed loosely; see ATTRIBUTION.md.

export const PluginLoader: any = {
	loadExternal: async () => {
		throw new Error("external plugins are disabled in atlas-terminal")
	},
}
