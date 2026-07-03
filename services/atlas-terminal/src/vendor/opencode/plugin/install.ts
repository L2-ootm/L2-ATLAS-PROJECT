// ATLAS shim — donor external-plugin/server machinery is intentionally
// disabled (no second runtime). Typed loosely; see ATTRIBUTION.md.

export const installPlugin: any = async () => {
	throw new Error("external plugins are disabled in atlas-terminal")
}
export const patchPluginConfig: any = async () => undefined
export const readPluginManifest: any = async () => undefined
