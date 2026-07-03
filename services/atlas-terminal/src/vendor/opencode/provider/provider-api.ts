// ATLAS shim adapted from ATLAS (MIT). Type/helper surface only —
// no donor server/runtime logic. See ATTRIBUTION.md.

export function parseModel(model: string): { providerID: string; modelID: string } {
	const [providerID, ...rest] = model.split("/")
	return { providerID: providerID ?? "", modelID: rest.join("/") }
}
