# hermes-rs — Rust Port Reference Intake

Date: 2026-06-11
Status: research input (not canonical; posture below requires no ADR until
code is actually reused)
Source: https://github.com/eikarna/hermes-rs (verified 2026-06-11)

## What it is

Community (unofficial, not Nous-affiliated) Rust rewrite of the Hermes-Agent
orchestration framework. Adopts the original's orchestration logic, system
prompts, and architecture for ReAct-loop agent execution.

- Language: Rust (~99%)
- License: dual **Apache-2.0 / MIT** — compatible with ATLAS reuse with
  attribution
- Maturity: v0.1.3 (2026-04-20), 43 stars, 73 commits — young, single-digit
  contributor scale
- Structure: `/crates` workspace; `hermes-core` (streaming, tool registry,
  schema generation), `hermes-cli` (TUI on **Ratatui**); MCP integration,
  TOML config with env fallbacks, autonomous workspace mode

## Relevance to ATLAS (D-022 L0–L5 ladder)

The ladder's end state is a Rust harness core strangling the Python agent
loop (v2.x). hermes-rs is a useful **reference map** for that port:

1. **Crate decomposition** — their core/cli split previews how our
   `crates/atlas-harness-core` / `crates/atlas-cli` boundary can look.
2. **Tool registry + schema generation in Rust** — directly relevant to
   re-expressing the foundation tool surface.
3. **Ratatui TUI** — candidate substrate for the future Rust ATLAS CLI
   (L5), where we re-apply the L2 skin system natively.
4. **What NOT to take**: it is a from-scratch reimplementation at v0.1.x —
   adopting it wholesale would violate D-018 (our foundation is the proven
   Python Hermes, evolved in place). Reuse is selective, file-level, with
   attribution.

## Posture

- **Reference, not vendor.** Clone to `_EXTERNAL_REPOS/hermes-rs`
  (gitignored) when port work starts; diff ideas, do not import trees.
- Any code-level reuse: per-file attribution + entry in
  `foundation/DIVERGENCE_LOG.md` or the receiving crate's ATTRIBUTION
  section, plus an ADR if it changes the L0–L5 ladder sequencing.
- Track upstream: at v0.1.x its API will churn; pin any referenced SHA.
