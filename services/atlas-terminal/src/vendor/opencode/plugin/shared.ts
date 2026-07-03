// ATLAS shim — donor external-plugin/server machinery is intentionally
// disabled (no second runtime). Typed loosely; see ATTRIBUTION.md.

export type PluginPackage = any
export type PluginSource = any
export const readPackageThemes: any = async () => ({})
export const readPluginId: any = async () => undefined
export const readV1Plugin: any = async () => undefined
export const resolvePluginId: any = async () => ""
export const isPathPluginSpec: any = () => false
export const parsePluginSpecifier: any = (spec: any) => ({ name: String(spec ?? ""), version: undefined })
export const resolvePathPluginTarget: any = () => ""
