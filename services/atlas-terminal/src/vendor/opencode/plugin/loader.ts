// ATLAS shim — external plugin loading disabled: resolves to no plugins
// instead of throwing so boot stays clean.
export const PluginLoader: any = {
	loadExternal: async () => [],
}
