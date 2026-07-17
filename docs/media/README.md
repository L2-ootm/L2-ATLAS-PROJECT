# Media assets

Production media set for README, repository metadata, and distribution posts.
Generated 2026-07-17 with OpenAI Codex CLI image generation (`codex exec`,
built-in imagegen skill), prompted against the L2 Systems topographic design
language. The exact prompt for every asset lives in `prompts/<name>.txt` —
regenerating an asset means re-running its prompt, not improvising a new one.

## Inventory

| File | Use case | Aspect |
|------|----------|--------|
| `atlas-hero.png` | README hero banner (wired into the root README) | 3:2 landscape |
| `atlas-og.png` | GitHub social preview — upload in repo Settings > Social preview; also OpenGraph card for link shares | 3:2 landscape |
| `atlas-social-x.png` | X/Twitter launch or release post (`$ atlas up` terminal card) | 3:2 landscape |
| `atlas-social-square.png` | LinkedIn / Instagram square post | 1:1 |
| `atlas-banner-wide.png` | Profile or channel banner; critical content held in the vertical center band for platform crops | 3:2 landscape |
| `atlas-avatar.png` | Avatar / app icon mark (contour-line "A"); legible at 64px | 1:1 |
| `atlas-feature-actors.png` | Feature card: durable actors — supervisor constellation with one recovering worker | 3:2 landscape |
| `atlas-feature-modules.png` | Feature card: module framework — cockpit pages materializing from manifests | 3:2 landscape |
| `atlas-feature-surfaces.png` | Feature card: one system, three surfaces (WEB / TUI / CLI) | 3:2 landscape |
| `atlas-feature-audit.png` | Feature card: audit ledger — every action on the record | 3:2 landscape |
| `atlas-install.png` | Install promo (`npm i -g @l2/atlas`) for posts and docs | 3:2 landscape |
| `atlas-wallpaper.png` | Operator desktop wallpaper; very dark, icon-safe | 3:2 landscape |

Still owed (not generatable — must be a real capture): `atlas-cockpit.png`,
the WebUI cockpit screenshot strip for the second README slot. Take it from a
live cockpit session; do not substitute a generated mock for a product
screenshot.

## Conventions

- Keep filenames stable so links never break.
- Brand constants used by every prompt: void black `#030305`–`#050505`
  canvas, 1px blue-gray `#20242e` contour terrain, electric violet `#7B61FF`
  primary, cyan `#00F0FF` / green `#00FF94` / amber `#FFD600` as semantic
  signals only, obsidian glass slabs, sharp 2px corners, monospace data
  voice, no warm tones, no emoji.
- Landscape masters are 1536×1024; crop or downscale per platform at post
  time rather than regenerating.
