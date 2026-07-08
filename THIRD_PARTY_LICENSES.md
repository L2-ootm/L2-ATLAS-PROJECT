# Third-Party Licenses

ATLAS (this repository) is licensed under the [MIT License](LICENSE). This
document lists the **direct** (non-transitive) third-party dependencies of
ATLAS's first-party packages/services, their licenses, and the attribution
required by each license family. It does not cover vendored/derived
codebases (Hermes foundation, MiMo-Code terminal donor, L2-BOT) — those are
tracked separately in [`ATTRIBUTION.md`](ATTRIBUTION.md), nor does it cover
`_EXTERNAL_REPOS/` (gitignored audit copies, never published) or transitive
dependencies pulled in by the packages listed below.

Scope: `packages/atlas-core`, `services/agent-runtime`, `services/wiki-runtime`
(Python); `packages/atlas-cli`, `services/web-ui-react`, `services/cashflow`,
`services/atlas-terminal` (Node); `native/atlas-core-rs` and
`services/web-ui-react/src-tauri` (Rust).

**Methodology:** licenses were read directly from installed package metadata
on disk (`node_modules/*/package.json`, Python `*.dist-info/METADATA`) or
from `Cargo.lock` cross-referenced with each crate's published license
metadata, not inferred from memory. Where a license grants copyright to
"the respective package authors," the authoritative copyright holder and
notice live in that package's own repository/registry page (linked per
license family below); this document does not restate 60+ individual
copyright lines, consistent with standard NOTICE-file practice for
monorepos with permissively-licensed dependency trees.

---

## ⚠️ Flags — require manual review (not silently classified)

| Package | Ecosystem | Issue |
|---|---|---|
| **fastembed** 0.8.0 | Python (optional `semantic` extra of `atlas-wiki`) | Metadata is internally inconsistent: the free-text `License:` header says "Apache License," but the package also ships `Classifier: License :: Other/Proprietary License` with **no** OSI Apache classifier. This is not a clean SPDX declaration. Do not publish this dependency as plain Apache-2.0 without manually inspecting the `LICENSE`/`NOTICE` files bundled in the wheel or the upstream repo. |
| **sqlite-vec** 0.1.9 | Python (optional `semantic` extra of `atlas-wiki`) | Declared dual "MIT License, Apache License, Version 2.0" via free-text (not SPDX expression), and metadata contains placeholder `Home-page: https://TODO.com` / `Author: TODO` fields — upstream metadata appears unfinished. Not copyleft, but worth a quick manual check against the actual repo before treating the dist-info text as final. |
| **@fontsource/cinzel, @fontsource/cormorant-garamond, @fontsource/inter, @fontsource/jetbrains-mono** | Node (`web-ui-react`) | Licensed under **OFL-1.1** (SIL Open Font License), not a general code license. Compatible with MIT distribution (no reciprocal clause), but has font-specific terms (no standalone resale as a font product, Reserved Font Name mechanics) — see the OFL-1.1 text below. |

No GPL, LGPL, AGPL, MPL, EPL, or CDDL (copyleft) dependencies were found in
any direct dependency across Python, Node, or Rust.

---

## Python — direct dependencies

| Package | Version | License | Used by |
|---|---|---|---|
| pydantic | 2.13.4 | MIT | atlas-core |
| typer | 0.25.1 | MIT | atlas-runtime, atlas-wiki |
| PyYAML | 6.0.3 | MIT | atlas-runtime |
| claude-agent-sdk | 0.2.104 | MIT | atlas-runtime (optional `claude` extra) |
| sqlite-vec | 0.1.9 | MIT / Apache-2.0 (dual — see flag above) | atlas-wiki (optional `semantic` extra) |
| fastembed | 0.8.0 | Ambiguous — see flag above | atlas-wiki (optional `semantic` extra) |

## Node — direct production dependencies

### packages/atlas-cli
No runtime dependencies (Node built-ins only).

### services/web-ui-react

| Package | Version | License |
|---|---|---|
| 3d-force-graph | 1.80.0 | MIT |
| @fontsource/cinzel | 5.2.8 | OFL-1.1 |
| @fontsource/cormorant-garamond | 5.2.11 | OFL-1.1 |
| @fontsource/inter | 5.2.8 | OFL-1.1 |
| @fontsource/jetbrains-mono | 5.2.8 | OFL-1.1 |
| lucide-react | 1.20.0 | ISC |
| ogl | 1.0.11 | Unlicense |
| react | 19.2.7 | MIT |
| react-dom | 19.2.7 | MIT |
| react-router-dom | 7.18.0 | MIT |
| three | 0.184.0 | MIT |
| three-spritetext | 1.10.0 | MIT |

### services/cashflow

| Package | Version | License |
|---|---|---|
| @modelcontextprotocol/sdk | 1.29.0 | MIT |
| @opengsd/gsd-core | 1.4.4 | MIT |
| @supabase/supabase-js | 2.108.2 | MIT |
| better-sqlite3 | 12.6.2 | MIT |
| clsx | 2.1.1 | MIT |
| docx | 9.7.1 | MIT |
| framer-motion | 12.34.4 | MIT |
| jspdf | 4.2.0 | MIT |
| jspdf-autotable | 5.0.7 | MIT |
| lucide-react | 0.575.0 | ISC |
| next | 16.1.6 | MIT |
| postcss | 8.5.6 | MIT |
| react | 19.2.3 | MIT |
| react-dom | 19.2.3 | MIT |
| recharts | 3.7.0 | MIT |
| tailwind-merge | 3.5.0 | MIT |

### services/atlas-terminal

| Package | Version | License |
|---|---|---|
| @effect/platform-node | 4.0.0-beta.48 | MIT |
| @opentui/core | 0.1.99 | MIT |
| @opentui/solid | 0.1.99 | MIT |
| @solid-primitives/event-bus | 1.1.3 | MIT |
| @solid-primitives/i18n | 2.2.1 | MIT |
| @solid-primitives/scheduled | 1.5.3 | MIT |
| cli-sound | 1.1.3 | MIT |
| clipboardy | 5.3.1 | MIT |
| cross-spawn | 7.0.6 | MIT |
| effect | 4.0.0-beta.48 | MIT |
| fuzzysort | 3.1.0 | MIT |
| jsonc-parser | 3.3.1 | MIT |
| mime-types | 3.0.2 | MIT |
| open | 11.0.0 | MIT |
| opentui-spinner | 0.0.6 | MIT |
| pinyin-pro | 3.28.1 | MIT |
| pngjs | 7.0.0 | MIT |
| remeda | 2.26.0 | MIT |
| semver | 7.7.4 | ISC |
| solid-js | 1.9.9 | MIT |
| strip-ansi | 7.2.0 | MIT |
| xdg-basedir | 5.1.0 | MIT |
| zod | 4.1.8 | MIT |

## Rust — direct dependencies

Versions read from committed `Cargo.lock` files; licenses per each crate's
published `Cargo.toml` `license` metadata on crates.io.

### native/atlas-core-rs (crate: atlas-gateway)

| Crate | Version | License |
|---|---|---|
| axum | 0.8.9 | MIT |
| tokio | 1.52.3 | MIT |
| serde | 1.0.228 | MIT OR Apache-2.0 |
| serde_json | 1.0.150 | MIT OR Apache-2.0 |
| rusqlite | 0.32.1 | MIT |
| futures-util | 0.3.32 | MIT OR Apache-2.0 |
| tower (dev) | 0.5.3 | MIT |
| http-body-util (dev) | 0.1.3 | MIT |
| tempfile (dev) | 3.27.0 | MIT OR Apache-2.0 |

### services/web-ui-react/src-tauri

| Crate | Version | License |
|---|---|---|
| serde | 1.0.228 | MIT OR Apache-2.0 |
| serde_json | 1.0.150 | MIT OR Apache-2.0 |
| log | 0.4.32 | MIT OR Apache-2.0 |
| tauri | 2.11.3 | MIT OR Apache-2.0 |
| tauri-plugin-log | 2.8.0 | MIT OR Apache-2.0 |
| rfd | 0.15.4 | MIT |
| tauri-build (build-dep) | 2.6.3 | MIT OR Apache-2.0 |

---

## License texts and attribution requirements

### MIT License (applies to all packages above marked "MIT")

Permission is hereby granted, free of charge, to any person obtaining a copy
of the software and associated documentation files, to deal in the software
without restriction, including without limitation the rights to use, copy,
modify, merge, publish, distribute, sublicense, and/or sell copies, subject
to including the original copyright notice and this permission notice in
all copies or substantial portions. THE SOFTWARE IS PROVIDED "AS IS",
WITHOUT WARRANTY OF ANY KIND. Copyright is held by each package's respective
authors; see the package's own repository (linked from its npm/PyPI/
crates.io page) for the exact copyright line.

### ISC License (lucide-react, semver)

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies. THE
SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES.

### Apache License 2.0 (dual-licensed Rust crates, "MIT OR Apache-2.0")

Where a crate is dual-licensed MIT/Apache-2.0, ATLAS exercises the MIT
option for consistency with the rest of the codebase. Apache-2.0 full text:
https://www.apache.org/licenses/LICENSE-2.0

### Unlicense (ogl)

This is free and unencumbered software released into the public domain.
No attribution is legally required; full text: https://unlicense.org/

### SIL Open Font License 1.1 (@fontsource/cinzel, @fontsource/cormorant-garamond, @fontsource/inter, @fontsource/jetbrains-mono)

Copyright notices are embedded in each font's own OFL.txt (bundled by the
`@fontsource/*` packages). The fonts may be used, studied, modified, and
redistributed freely, including in commercial products, but **may not be
sold by themselves** as a standalone font product, and modified versions
must not use the Reserved Font Name. Full text:
https://openfontlicense.org/open-font-license-official-text/

---

## Updating this file

This file is a point-in-time snapshot (generated 2026-07-08). It covers
direct dependencies only; if a first-party `package.json`/`pyproject.toml`/
`Cargo.toml` gains or removes a direct runtime dependency, this file should
be regenerated/updated in the same PR.
