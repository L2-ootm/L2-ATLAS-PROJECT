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

### Set 2 — 2026-07-17 (ATLAS celestial identity, fusion, WebUI-integrated)

Set 2 adds the ATLAS-native celestial engraved identity (canon references in
`brand/atlas/`), fusion pieces that translate the Atlas Bearer into the L2
topographic language, and compositions that integrate the real WebUI via
reference screenshots. Reference-driven prompts note their refs inline.

| File | Use case | Aspect |
|------|----------|--------|
| `atlas-cockpit.png` | **Real screenshot** (cropped Observatory hero band, no mission data) — wired into the root README cockpit slot | wide strip |
| `atlas-emblem-hero.png` | ATLAS celestial hero — wordmark + Atlas Bearer emblem (ref: `brand/atlas/marks/emblem-figure.png`) | 3:2 landscape |
| `atlas-seal-bronze.png` | Governance seal as physical bronze medallion macro (ref: `brand/atlas/marks/seal.png`) — stickers, coins, about pages | 1:1 |
| `atlas-celestial-banner.png` | Wide celestial banner — bearer + orbit arcs + "FOR THOSE WHO BUILD WHAT ENDURES." | 3:2 landscape |
| `atlas-pillars-poster.png` | MISSION / AUDIT / STRUCTURE pillars poster (ref: brand master sheet) | 2:3 portrait |
| `atlas-monogram-star.png` | Celestial "A" monogram icon (ref: celestial mark system sheet) | 1:1 |
| `atlas-fusion-bearer.png` | Fusion poster — the Bearer re-materialized as violet contour lines rising from terrain | 2:3 portrait |
| `atlas-fusion-summit.png` | Fusion — celestial sphere docking onto a topographic summit ("STRUCTURE MEETS TERRITORY") | 3:2 landscape |
| `atlas-feature-goal.png` | Feature card: /goal missions — switchback path with judge gates | 3:2 landscape |
| `atlas-feature-mesh.png` | Feature card: provider mesh — API KEY / OAUTH / SIDECAR / LOCAL braided into one | 3:2 landscape |
| `atlas-release-card.png` | Reusable release-announcement template (v1.0 placeholder) | 3:2 landscape |
| `atlas-cockpit-showcase.png` | Real cockpit UI as floating obsidian monolith over terrain (ref: live screenshot, small text abstracted) | 3:2 landscape |
| `atlas-cockpit-observatory.png` | Cinematic: operator silhouette before a monumental cockpit wall (ref: live screenshot, small text abstracted) | 3:2 landscape |

WebUI-integrated pieces deliberately abstract all small interface text to
placeholder dashes — the source captures contain private mission prompts.
Only `atlas-cockpit.png` is an untouched real capture, cropped above the
mission list for that reason.

## Conventions

- Keep filenames stable so links never break.
- Brand constants used by every prompt: void black `#030305`–`#050505`
  canvas, 1px blue-gray `#20242e` contour terrain, electric violet `#7B61FF`
  primary, cyan `#00F0FF` / green `#00FF94` / amber `#FFD600` as semantic
  signals only, obsidian glass slabs, sharp 2px corners, monospace data
  voice, no warm tones, no emoji.
- Landscape masters are 1536×1024; crop or downscale per platform at post
  time rather than regenerating.
