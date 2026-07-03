declare global {
  const ATLAS_TUI_VERSION: string
  const ATLAS_TUI_CHANNEL: string
}

export const InstallationVersion = typeof ATLAS_TUI_VERSION === "string" ? ATLAS_TUI_VERSION : "local"
export const InstallationChannel = typeof ATLAS_TUI_CHANNEL === "string" ? ATLAS_TUI_CHANNEL : "local"
export const InstallationLocal = InstallationChannel === "local"
