# Omni-Surface Wiring Strategy

## Overview

L2 ATLAS is fundamentally a multi-surface workbench (Web Cockpit, Terminal User Interface, CLI, and Discord). The core architectural mandate is that **the entire system must be flawlessly wired to a single, unified source of truth**, while allowing each surface to maintain its native, platform-specific UX ("slight differences"). 

ATLAS is built on the strict principle that **we do not deploy messy, temporary fixes**. The architecture must be robust, permanent, and intrinsically cohesive. 

## 1. Unified Internal Engine (No Black-Box Shelling)

ATLAS must never treat its foundational donors (Hermes, MiMo-Code, OpenCode) as black-box external executables. 

- **The Anti-Pattern:** Shelling out to an external CLI (e.g., `hermes run`) via `subprocess` and relying on OS-level environment variables (like `FREELLMAPI_API_KEY`) is strictly forbidden. It fragments the state and breaks cross-surface cohesion.
- **The Solution:** ATLAS incorporates the MIT-licensed logic from these donor projects *directly* into its own native runtime. The final ATLAS engine natively owns the mission execution, prompt building, and model routing.

## 2. Centralized State and Configuration

For the system to work seamlessly across all surfaces, the configuration layer must be singular and absolute.

- **Single Source of Truth:** All configurations (API keys, provider settings, reasoning effort, function routing) are managed by the ATLAS Rust Gateway and stored in the secure local SQLite databases (e.g., `registry.db`).
- **Instant Cross-Surface Sync:** If a user updates their FreeLLMAPI configuration in the Web Cockpit, the TUI and Discord surfaces must immediately route through the new configuration without requiring restarts or environment variable hacks. 
- **Unified Sessions:** A mission started in the TUI can be monitored in the Web Cockpit. Audit logs and approval queues are universally accessible regardless of the originating surface.

## 3. Surface-Specific UX (Slight Differences)

While the backend logic and state are monolithic, the presentation layer must be deeply tailored to the medium.

- **Web Cockpit (React):** Rich, visual, mouse-driven. Uses topographic design tokens, glass panels, and interactive dashboards. Optimized for deep visual configuration and data review (Cashflow, Wiki).
- **Terminal UI (Go/BubbleTea):** Keyboard-centric, hyper-fast, low-latency. Employs terminal-native mechanics (starfield twinkling, meteors, glyph gradients, slash commands). Interacts intimately with the local filesystem and Git repositories.
- **Discord:** Asynchronous, mobile-friendly, and thread-based. Relies on embed cards and webhook updates for team collaboration.

## 4. The Engineering Standard

- **No Temp Fixes:** Workarounds that bypass the architecture (e.g., hardcoding paths, injecting OS environment variables to fix a crash) are unacceptable. If a component fails to read the central state, the component must be rewired, not patched.
- **Modular Autonomy:** Each surface adapter should be thin. It should translate user intent into the unified backend API, and translate backend audit streams into native UI components. The logic stays in the engine.
