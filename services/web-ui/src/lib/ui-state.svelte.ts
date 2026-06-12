// Shared cockpit shell UI state (Svelte 5 runes module).
// The sidebar is position:fixed, so the layout must track its width to keep
// main content from being occluded when expanded.

export const sidebar = $state({ expanded: false });

export const SIDEBAR_WIDTH_COLLAPSED = 56;
export const SIDEBAR_WIDTH_EXPANDED = 200;
