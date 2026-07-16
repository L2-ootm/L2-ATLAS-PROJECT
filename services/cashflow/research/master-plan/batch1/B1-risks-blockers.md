# B1 — Master Risk Register: L2 Cashflow Modular Platform

> Generated 2026-07-10 · Derived from 42 research findings (590+ sources) · 7 research reports
> Current state: Next.js 16 + React 19 + SQLite/Supabase (17 tables) · Internal L2 FinOps tool
> Target state: Universal modular cashflow platform (42 modules, 7 layers, multi-tenancy, SaaS)

---

## Executive Summary

This document identifies 38 discrete risks across 10 categories, prioritized by probability and impact. The top 5 existential risks are: (1) compliance timeline uncertainty around Brazil's tax reform (CBS/IBS) could force architectural rework mid-build, (2) event sourcing adoption is a foundational bet that may not pay off given the team's current expertise, (3) plugin system complexity may exceed what a small team can ship in a reasonable timeframe, (4) migration from the existing SQLite/17-table schema to PostgreSQL with event sourcing is a high-risk bridge that cannot fail, and (5) the Brazilian compliance knowledge gap (SPED, NFe, eSocial) is a hard blocker without domain experts.

---

## 1. Technical Risks

### R1 — Database Migration: SQLite → PostgreSQL + Event Sourcing

| Field | Value |
|---|---|
| **Probability** | H |
| **Impact** | H |
| **Category** | Technical |

**Description**: The current schema is 17 SQLite tables designed for an internal AI FinOps tool (client_accounts, usage_events, billing_events, etc.). The target requires PostgreSQL with RLS multi-tenancy, event sourcing for the ledger, CQRS materialized views, and a hybrid core+extension+JSONB schema. This is a full rewrite, not a migration.

**Why high probability**: The existing schema has no tenant isolation (single-tenant), uses TEXT primary keys instead of UUIDs, has no event store, and the table design is tightly coupled to the AI FinOps domain (not a universal cashflow).

**Impact if it fails**: Everything downstream depends on the database schema. Wrong schema = wrong API = wrong UI = wrong compliance output. A mid-flight schema correction after module development begins could invalidate months of work.

**Mitigation**:
- Build a schema evolution prototype (2-3 days) before any module development
- Define the core schema as a contract (interfaces/types) that modules code against
- Use Prisma migrate deploy with advisory locks for safe production migrations
- Expand-contract pattern: add new tables alongside old ones, migrate data, drop old
- Event sourcing for ledger only (append-only audit trail), not for all modules

---

### R2 — Event Sourcing Adoption Risk

| Field | Value |
|---|---|
| **Probability** | H |
| **Impact** | M |
| **Category** | Technical |

**Description**: The technical report recommends event sourcing for the ledger principal (append-only audit trail) with CQRS for read optimization. Event sourcing fundamentally changes how data is written, queried, and debugged. The team has no event sourcing experience.

**Why high probability**: Event sourcing is architecturally invasive. Every write path becomes an event emission. Queries require materialized views or projections. Debugging requires event replay. The team's current codebase has zero event-driven patterns.

**Impact if it fails**: Not catastrophic (can fall back to traditional CRUD) but creates technical debt and architectural confusion if partially adopted.

**Mitigation**:
- Prototype event sourcing for journal entries only (the single most audit-sensitive module)
- Keep traditional CRUD for non-financial data (users, settings, notifications)
- Time-box the prototype to 1 week; if it doesn't prove its value, use traditional schema
- Use Redis Streams for event bus (proven, not exotic) rather than custom event store
- Document the decision explicitly in an ADR before committing

---

### R3 — Plugin System Complexity

| Field | Value |
|---|---|
| **Probability** | H |
| **Impact** | H |
| **Category** | Technical |

**Description**: The target architecture requires a TOML manifest-driven plugin system with Odoo-style auto-install bridges, VS Code-style contribution points, Cargo SemVer, lifecycle hooks (pre_init → post_init → activate → deactivate → uninstall), and tiered loading (compile-time, hot-loadable, event-driven).

**Why high probability**: This is essentially building a mini-application framework within the application. WordPress, Odoo, and VS Code spent years refining their plugin systems. Building one that works for financial modules (where incorrect behavior = financial loss) is exceptionally hard.

**Impact if it fails**: The entire modular architecture collapses. Without a working plugin system, modules can't be independently activatable, the marketplace can't exist, and the platform is just a monolith with feature flags.

**Mitigation**:
- Start with a "module registry" pattern (database table tracking enabled modules) rather than a full plugin SDK
- Build the plugin system incrementally: Phase 1 = module enable/disable via config, Phase 2 = lifecycle hooks, Phase 3 = contribution points
- Use the existing Next.js module federation or dynamic imports for route-level module loading
- Defer the full marketplace/SDK until 10+ core modules are stable
- Reference Odoo's architecture but simplify aggressively (no hot-reloading in production)

---

### R4 — Performance at Scale (42 Modules)

| Field | Value |
|---|---|
| **Probability** | M |
| **Impact** | H |
| **Category** | Technical |

**Description**: 42 modules each contributing routes, event handlers, API endpoints, and database queries. With multi-tenancy, every query carries a tenant filter. Materialized views need refreshing. Event bus needs to handle cross-module communication without becoming a bottleneck.

**Why medium probability**: The system targets SMBs (not enterprise-scale). Brazilian micro/ME businesses have <50 transactions/day. Performance is unlikely to be the binding constraint early.

**Impact if it fails**: Slow dashboards kill SaaS adoption. Financial users expect instant balance lookups.

**Mitigation**:
- PgBouncer transaction pooling (5-10x connection efficiency)
- Composite indexes with INCLUDE for index-only scans (60-80% I/O reduction)
- Materialized views for reports (2-5s → 50-200ms)
- Cache TTLs: balances 5min, P&L 15min, COA 1h
- Partition journal_entries by fiscal period for query pruning
- Load test with realistic data (100k journal entries, 10 tenants) before GA

---

### R5 — Next.js 16 + React 19 Maturity Risk

| Field | Value |
|---|---|
| **Probability** | M |
| **Impact** | L |
| **Category** | Technical |

**Description**: The current stack uses Next.js 16.1.6 and React 19.2.3. These are very recent versions. Server Components, Server Actions, and the App Router patterns are still evolving. Plugin-like dynamic route loading with module manifests is an unusual pattern for Next.js.

**Mitigation**:
- Pin versions and test upgrades in a branch before pulling
- Keep module routing simple (dynamic imports, not exotic patterns)
- Budget 2-3 days for each major Next.js/React upgrade during the project

---

## 2. Compliance Risks

### R6 — Tax Reform (CBS/IBS) Timeline Uncertainty

| Field | Value |
|---|---|
| **Probability** | H |
| **Impact** | H |
| **Category** | Compliance |

**Description**: Brazil's tax reform (Complementary Law 214/2025) replaces PIS/COFINS/ICMS/ISS with CBS (federal) and IBS (state) over a transition period through 2033. The exact transition rates, credit mechanisms, and anti-abuse rules are still being defined by regulation. Building a tax engine that handles the current 9+ tax regime AND the incoming CBS/IBS dual-transition is architecturally complex.

**Why high probability**: The reform is law but the regulation is incomplete. The Receita Federal is issuing rules in batches. The technical report already identifies PIS/COFINS rates (1.65%/0.65% non-cumulative, 7.6%/3.0% cumulative) as current — these will change.

**Impact if it fails**: Tax miscalculation = legal liability. A tax engine built for the wrong regime is worse than no tax engine.

**Mitigation**:
- Design the tax engine as a rule-based config (JSONB rules with effective dates), not hardcoded logic
- Build a "tax rule versioning" system from day 1 (rules have valid_from/valid_to)
- Start with the stable tax regimes (IRPJ, CSLL, INSS) and defer PIS/COFINS/ICMS to Phase 2
- Monitor Receita Federal's publication cadence — budget quarterly rule updates
- Engage a Brazilian tax consultant (contador) for rule validation

---

### R7 — SPED Format Changes

| Field | Value |
|---|---|
| **Probability** | H |
| **Impact** | M |
| **Category** | Compliance |

**Description**: SPED (Sistema Publico de Escrituracao Digital) uses fixed-width pipe-delimited format with 4 books (ECD, ECF, EFD-Contribuicoes, EFD-ICMS IPI). The Receita Federal updates SPED layouts periodically. The ECD blocks (A, C, E, J), EFD records (A100, A170, M100, M200, M500, M600, C100, C170, E110, E200, E300, E500, E520) all have specific positional formats.

**Why high probability**: SPED layouts have changed multiple times (v016, v017, etc.). Each version requires parser updates.

**Mitigation**:
- Build SPED as a separate module with its own schema version tracking
- Use XSD validation in CI (automated, not manual)
- Golden master snapshot tests for SPED output
- Subscribe to Receita Federal's SPED changelog/RDO notifications
- Budget 2-4 weeks per SPED layout update

---

### R8 — NFS-e Municipal Fragmentation

| Field | Value |
|---|---|
| **Probability** | H |
| **Impact** | M |
| **Category** | Compliance |

**Description**: 5,570 municipalities with potentially different NFS-e implementations. The research identifies ABRASF 2.02/2.03/2.04 variants across SP, RJ, BH, Curitiba alone. Each has different ISS rates, tax codes, and RPS flows.

**Why high probability**: This is the most fragmented compliance requirement in the Brazilian tax system.

**Mitigation**:
- Prioritize the top 100 municipalities (covering 80%+ of economic activity)
- Design NFS-e as a pluggable renderer per municipality (one template = one city)
- Use ABRASF 2.03 as the baseline and handle deviations per city
- Allow users to manually submit NFS-e for unsupported municipalities
- Budget 1-2 weeks per municipality implementation

---

### R9 — eSocial v.S-1.3 Layout Changes

| Field | Value |
|---|---|
| **Probability** | M |
| **Impact** | H |
| **Category** | Compliance |

**Description**: eSocial v.S-1.3 went to production 01/07/2026 (4 days ago). Layout changes include alphanumeric CNPJ and new event structures. The payroll module must handle S-1200 (remuneration), S-1210 (payments), S-1299 (periodic closure), and DCTFWeb auto-generation.

**Mitigation**:
- Use the official eSocial schema validation (XSD) in CI
- Subscribe to eSocial's technical bulletins
- Build eSocial as a separate module with its own version tracking
- Phase payroll module after core financial modules are stable

---

### R10 — IFRS 18 (2027) Preparation

| Field | Value |
|---|---|
| **Probability** | M |
| **Impact** | M |
| **Category** | Compliance |

**Description**: IFRS 18 (effective 2027) introduces new Mandatory Performance Measures (MPMs) and disaggregation requirements for the income statement. The platform should support this from the start to avoid refactoring.

**Mitigation**:
- Design the reporting engine with pluggable standards (IFRS 15/16/17/18 as separate adjustment layers)
- The Multi-GAAP architecture (base ledger + adjustment layers + reporting views) handles this naturally
- Budget 4-6 weeks for IFRS 18 implementation in the reporting module

---

## 3. Business Risks

### R11 — Pricing Strategy Validation

| Field | Value |
|---|---|
| **Probability** | H |
| **Impact** | H |
| **Category** | Business |

**Description**: The research recommends hybrid tiered + per-module pricing (Free/R$79/R$199/R$499 + add-ons). Brazilian SMBs pay 40-60% less than US equivalents. The pricing model has NOT been validated with real users. The "Rule of 3" (Decoy/Hero/Anchor) is theoretical.

**Why high probability**: No pricing research has been conducted with actual Brazilian business owners. The sweet spot (R$50-150 for micro/small, R$200-500 for medium) is based on competitor analysis, not willingness-to-pay research.

**Impact if it fails**: Wrong pricing = wrong unit economics = can't fund development. Overpricing kills adoption; underpricing kills sustainability.

**Mitigation**:
- Run a pricing survey with 50-100 Brazilian business owners before building the billing module
- Use the intro pricing (60-80% off 3 months) as the primary lever
- Start with freemium to validate adoption before optimizing for revenue
- Benchmark against actual competitor prices (QuickBooks ~R$100, Xero ~R$130, FreshBooks ~R$60)
- Price the core cheaply and monetize compliance modules (SPED, NFe, eSocial)

---

### R12 — Market Fit: Cashflow-First vs Accounting-First

| Field | Value |
|---|---|
| **Probability** | M |
| **Impact** | H |
| **Category** | Business |

**Description**: The competitive analysis identifies that no platform is "cashflow-first" — all are accounting-first with bolt-on reporting. This is positioned as a differentiator. However, Brazilian businesses (especially MEIs and micro-enterprises) may not understand the distinction and may expect a full accounting tool.

**Mitigation**:
- Validate with 20+ interviews that "cashflow-first" resonates with the target market
- Ensure the core modules (GL, COA, invoicing) satisfy basic accounting needs
- Position as "financial management for non-accountants" rather than "cashflow-first"

---

### R13 — QuickBooks/Xero Entering Brazil

| Field | Value |
|---|---|
| **Probability** | M |
| **Impact** | M |
| **Category** | Business |

**Description**: QuickBooks already has a Brazilian presence. Xero operates in the region. If either accelerates Brazil-specific features (NFe, SPED, Pix), the window narrows.

**Mitigation**:
- Move fast on Brazil-native features (NFe, SPED, Pix, Boleto) — these are the moat
- Open-source the core to build community before incumbents catch up
- Focus on the SMB segment that incumbents price out

---

### R14 — Go-to-Market Ambiguity

| Field | Value |
|---|---|
| **Probability** | H |
| **Impact** | M |
| **Category** | Business |

**Description**: The research identifies 6 open questions about go-to-market: target market (MEIs first? mid-size? freelancers?), open-source %, and marketplace seed plugins. No decision has been made.

**Mitigation**:
- Decide target segment before building onboarding: MEIs are simplest (DAS MEI, fixed rates, low compliance complexity)
- Ship the core + MEI module first, then expand
- Use invoice-as-viral-vector (PLG) to drive organic growth

---

## 4. Resource Risks

### R15 — Developer Count and Expertise Gap

| Field | Value |
|---|---|
| **Probability** | H |
| **Impact** | H |
| **Category** | Resource |

**Description**: Building 42 modules across 7 layers with Brazilian compliance, event sourcing, plugin architecture, multi-tenancy, and SaaS infrastructure requires specialized knowledge in: (1) financial systems accounting, (2) Brazilian tax compliance, (3) event-driven architecture, (4) PostgreSQL RLS, (5) Rust (per D-022 cementation rule). The AGENTS.md states "Cement in Rust" for new infrastructure, but the current team's Rust capabilities are unclear.

**Why high probability**: The project is currently built by what appears to be a single developer (Davi). 42 modules with compliance requirements typically require 8-15 developers.

**Mitigation**:
- Hire 2-3 developers with Brazilian accounting/compliance domain knowledge
- At least 1 developer with Rust experience (for the native layer per D-005/D-022)
- Phase the work: build core modules first (GL, invoicing, AP/AR), defer industry modules
- Consider contractors for compliance modules (SPED, NFe, eSocial) where domain knowledge is critical
- Open-source parts of the project to attract community contributors

---

### R16 — Brazilian Compliance Domain Knowledge

| Field | Value |
|---|---|
| **Probability** | H |
| **Impact** | H |
| **Category** | Resource |

**Description**: Building SPED generators, NFe XML signers, and eSocial integrators requires deep knowledge of Brazilian fiscal regulations. A software developer without this knowledge will produce incorrect outputs, which has legal consequences for users.

**Mitigation**:
- Engage a licensed contador (accountant) as a consultant during compliance module development
- Use existing open-source SPED/NFe libraries as reference implementations (e-xsped, nfe-ws)
- Validate all compliance output against official Receita Federal validators
- Budget for legal review of compliance modules before GA

---

### R17 — Rust Expertise Availability

| Field | Value |
|---|---|
| **Probability** | M |
| **Impact** | H |
| **Category** | Resource |

**Description**: D-022 mandates Rust-first for new infrastructure. The native layer (D-005) is Rust. However, Rust developers with financial systems experience are rare in Brazil.

**Mitigation**:
- Identify which components actually need Rust (gateway, CLI, event store) vs Python/TypeScript
- Use Rust only for performance-critical or security-critical paths
- Consider hiring remotely (global Rust talent pool is larger)

---

## 5. Integration Risks

### R18 — SEFAZ API Availability and Changes

| Field | Value |
|---|---|
| **Probability** | H |
| **Impact** | H |
| **Category** | Integration |

**Description**: NFe 4.00 requires SOAP 1.2 with X.509 mutual TLS to 15 different SEFAZ autorizadores (SVAN, SVRS, SVC-AN, SVC-RS + 11 state-specific). Each state's SEFAZ has different uptime, different web service endpoints, and different error codes. SEFAZ frequently goes down during peak periods (last business day of month).

**Why high probability**: SEFAZ downtime is a known and common issue in Brazilian fiscal operations. State SEFAZ servers are not as reliable as cloud services.

**Mitigation**:
- Build a SEFAZ abstraction layer with retry logic and circuit breakers
- Queue NFe submissions during SEFAZ downtime (async processing)
- Implement status polling (NfeStatusServico) to detect outages before attempting submission
- Support fallback autorizadores (SVC-AN/SVC-RS as backup)
- Budget for SEFAZ-specific monitoring and alerting

---

### R19 — Open Finance API Instability

| Field | Value |
|---|---|
| **Probability** | M |
| **Impact** | M |
| **Category** | Integration |

**Description**: Open Finance Brasil for account aggregation is still maturing. API versions change, bank implementations vary, and consent flows add UX friction.

**Mitigation**:
- Use Belvo or similar aggregation API as an abstraction layer
- Offer OFX import as fallback for banks without Open Finance support
- Design the bank connection module as pluggable (add new providers without core changes)

---

### R20 — Payment Gateway Reliability

| Field | Value |
|---|---|
| **Probability** | L |
| **Impact** | H |
| **Category** | Integration |

**Description**: Payment processing (Stripe, PagSeguro, Mercado Pago) failures can cause lost revenue and reconciliation headaches. Gateway outages are infrequent but impactful.

**Mitigation**:
- Multi-gateway support from day 1 (Stripe + PagSeguro)
- Payment queue with retry logic for failed transactions
- Reconciliation reports that match gateway transactions against ledger entries
- Idempotency keys for all payment operations

---

## 6. Data Risks

### R21 — Migration from Existing Data

| Field | Value |
|---|---|
| **Probability** | H |
| **Impact** | H |
| **Category** | Data |

**Description**: The existing 17-table SQLite schema must be mapped to the new PostgreSQL schema. The existing data (client_accounts, contracts, usage_events, billing_events) is AI FinOps specific and needs to be transformed, not just migrated. Some tables may not map to any target table.

**Why high probability**: Schema mismatch between source and target is guaranteed. The existing data model is domain-specific (AI token tracking) while the target is generic (universal cashflow).

**Mitigation**:
- Build migration scripts that transform (not just copy) existing data
- Idempotent imports via content hashes (re-runnable without duplicates)
- Post-migration reconciliation: balance checks, record counts, audit log
- Support OFX/QFX/CNAB 240/400/QuickBooks IIF-QBO/Xero CSV for importing from other systems
- Defer data migration to Phase 2 — build the new system first, migrate later

---

### R22 — Data Integrity During Transition

| Field | Value |
|---|---|
| **Probability** | M |
| **Impact** | H |
| **Category** | Data |

**Description**: During the transition from old system to new system, data may be modified in both places, leading to inconsistency. Financial data must be perfectly accurate.

**Mitigation**:
- Run old and new systems in parallel during transition (read-only old system)
- Use feature flags to control which system serves production traffic
- Daily reconciliation reports during transition period
- Freeze old system modifications after migration date

---

### R23 — Backup and Disaster Recovery

| Field | Value |
|---|---|
| **Probability** | L |
| **Impact** | H |
| **Category** | Data |

**Description**: Financial data requires RPO <1 hour and RTO <4 hours. Backup strategy must cover PostgreSQL, Redis, and any file storage.

**Mitigation**:
- WAL archiving every 5 minutes + daily pg_basebackup
- Point-in-time recovery up to 30 days
- Automated restore scripts tested monthly
- Multi-region active-warm standby for production (Phase 3+)

---

## 7. Security Risks

### R24 — PCI DSS Scope

| Field | Value |
|---|---|
| **Probability** | M |
| **Impact** | H |
| **Category** | Security |

**Description**: If the platform processes credit card data directly, PCI DSS SAQ D applies (300+ controls). Using Stripe/Adyen tokenization reduces scope to SAQ A (~20-30 controls), but the platform still needs to handle token security, webhook signatures, and refund flows.

**Mitigation**:
- Use Stripe/Adyen tokenization exclusively (never touch raw card data)
- SAQ A scope from day 1
- PCI-compliant infrastructure (Vercel/AWS with PCI attestation)
- Annual PCI self-assessment

---

### R25 — SOC 2 Compliance Timeline

| Field | Value |
|---|---|
| **Probability** | M |
| **Impact** | M |
| **Category** | Security |

**Description**: Enterprise customers may require SOC 2 Type II compliance. This requires 6-12 months of operational evidence collection plus audit costs.

**Mitigation**:
- Start collecting evidence from day 1 (access logs, change logs, incident reports)
- Use Vercel + Supabase which already have SOC 2 attestations
- Budget 3-6 months and $20-50k for SOC 2 Type II audit when needed
- Target SOC 2 readiness by Year 2, not Year 1

---

### R26 — LGPD Compliance for Financial Data

| Field | Value |
|---|---|
| **Probability** | M |
| **Impact** | H |
| **Category** | Security |

**Description**: Brazil's LGPD (Lei Geral de Protecao de Dados) applies to all personal data. Financial data has minimum retention requirements (5-7 years) that conflict with LGPD's right to deletion.

**Mitigation**:
- Design retention policies by data type (financial records: 5-10 years; PII: minimal)
- Implement data masking for non-production environments (format-preserving encryption)
- Right to deletion with regulatory exception handling (financial records cannot be deleted)
- Privacy impact assessment before launch

---

### R27 — Penetration Testing

| Field | Value |
|---|---|
| **Probability** | M |
| **Impact** | H |
| **Category** | Security |

**Description**: Financial platforms are high-value targets. The plugin system adds attack surface. Multi-tenancy means one vulnerability can expose all tenants.

**Mitigation**:
- Third-party penetration test before GA
- RBAC + RLS for every tenant isolation boundary
- Envelope encryption (DEK/KEK) with AES-256-GCM
- Hash-chaining audit trail (tamper-evident)
- Rate limiting per API key (tiered quotas)

---

## 8. Scope Risks

### R28 — Feature Creep (42 Modules)

| Field | Value |
|---|---|
| **Probability** | H |
| **Impact** | H |
| **Category** | Scope |

**Description**: 42 modules across 7 layers is ambitious for any team. The temptation to build everything at once is high, especially with the comprehensive research already done.

**Why high probability**: The research is so thorough that every module feels equally important and ready to build.

**Mitigation**:
- Strict phased approach: Core (10 modules) → Compliance (6) → Operations (5) → Advanced (9) → Industry (8) → Integrations (6) → Automation (5)
- MVP scope: GL + COA + Invoicing + AP + AR + Bank Rec + Auth = 7 core modules
- Industry modules are deferred until core + compliance are stable
- Use Kalungi Feature Ranking Matrix: build High Popularity + High Uniqueness first
- Maximum 3 modules in parallel at any time

---

### R29 — Industry Module Complexity

| Field | Value |
|---|---|
| **Probability** | H |
| **Impact** | M |
| **Category** | Scope |

**Description**: 8 industry modules (Retail, SaaS, Manufacturing, Marketplace, Real Estate, Healthcare, Agriculture, Services) each with unique financial workflows. Manufacturing alone requires BOM, WIP, COGS allocation, and cost center tracking.

**Mitigation**:
- Industry modules are Phase 5 (last) — build core first
- Each industry module is optional and independently activatable
- Start with Services (simplest: time tracking, project billing) as the first industry module
- Manufacturing and Agriculture are the most complex — defer until community demand validates them

---

### R30 — Onboarding Wizard Complexity

| Field | Value |
|---|---|
| **Probability** | M |
| **Impact** | M |
| **Category** | Scope |

**Description**: The 5-step setup wizard (industry selection → tax regime → invoice template → bank connection → first invoice) requires industry-specific COA templates for every business type. Auto-generating a restaurant COA (45 accounts) vs a SaaS COA vs a manufacturing COA requires significant domain knowledge per industry.

**Mitigation**:
- Start with 3-5 COA templates (Services, Retail, SaaS, General)
- Defer industry-specific COAs to when those industry modules ship
- Allow manual COA customization (not just auto-generation)
- Ghost's progress bar pattern (1000% conversion improvement) is a quick win

---

## 9. Blockers (Must Resolve Before Development)

### B1 — Legal Entity and Compliance Responsibility

| Priority | MUST RESOLVE |
|---|---|
| **Type** | Legal |

**Description**: Who is legally responsible if the platform generates incorrect SPED files, miscalculates taxes, or produces invalid NFe? The platform cannot disclaim liability for financial accuracy if it's selling compliance as a feature.

**Actions required**:
- Legal opinion on liability scope (platform vs user responsibility)
- Terms of Service that clearly delineate responsibilities
- "Professional accountant review recommended" disclaimers on compliance outputs
- Insurance (D&O, E&O) if operating as a company

---

### B2 — Target Market Decision

| Priority | MUST RESOLVE |
|---|---|
| **Type** | Strategic |

**Description**: The research identifies 6 open questions about go-to-market. Without a target market decision, the module prioritization, pricing, and onboarding design are all ambiguous.

**Decision required**: MEIs first (simplest: DAS MEI, fixed rates, minimal compliance)? Small businesses (LTDA with SPED/NFe needs)? Mid-size (multi-entity, complex tax)?

**Recommendation**: Start with MEIs and micro-businesses (< R$80k/year revenue). Lowest compliance complexity, largest market segment, simplest onboarding.

---

### B3 — Open-Source vs Proprietary Decision

| Priority | MUST RESOLVE |
|---|---|
| **Type** | Strategic |

**Description**: How much of the platform is open-source? This affects: community building, marketplace economics, competitive moat, and revenue model.

**Decision required**: Core only open-source? All modules? Plugin SDK only?

**Recommendation**: Core (GL, COA, invoicing) open-source under AGPL or similar; compliance modules and industry modules proprietary. This builds community while maintaining revenue.

---

### B4 — Multi-Tenant Architecture Decision

| Priority | MUST RESOLVE |
|---|---|
| **Type** | Technical |

**Description**: Shared database with RLS for all tenants? Dedicated database for enterprise clients? This affects the entire data layer design.

**Decision required**: Shared DB + RLS (simpler, cheaper) vs hybrid (shared for SMB, dedicated for enterprise)?

**Recommendation**: Start with shared DB + PostgreSQL RLS. Add dedicated option for enterprise in Phase 3+. The research confirms PgBouncer requires SET app.tenant_id per transaction (not per connection) for RLS compatibility.

---

### B5 — Budget and Funding

| Priority | MUST RESOLVE |
|---|---|
| **Type** | Financial |

**Description**: Building 42 modules with compliance requirements requires significant investment. The AGENTS.md doesn't mention a budget or funding source.

**Estimated cost**:
- 2-3 developers: R$30-50k/month
- Compliance consultant: R$5-10k/month
- Infrastructure (Supabase/PostgreSQL/Redis): R$2-5k/month
- Penetration test: R$15-25k one-time
- Legal review: R$10-20k one-time
- SOC 2 audit (Year 2): R$100-200k

**Actions required**: Confirm available budget and timeline expectations.

---

## 10. Unknowns

### U1 — Market Validation

| Priority | HIGH |
|---|---|
| **Type** | Business |

**What we don't know**: Do Brazilian micro/small businesses actually want a modular cashflow platform? Or do they prefer simple invoicing tools (Nota Fiscal eletronica is mandatory, but accounting is often outsourced to a contador)?

**How to resolve**: Interview 30-50 Brazilian business owners. Ask: "Do you manage your own finances? What tools do you use? What's missing?"

---

### U2 — Regulatory Timeline (CBS/IBS)

| Priority | HIGH |
|---|---|
| **Type** | Compliance |

**What we don't know**: Exact transition rates, credit mechanisms, and anti-abuse rules for the CBS/IBS tax reform. The Receita Federal is issuing regulation in batches through 2033.

**How to resolve**: Subscribe to Receita Federal's consultation responses. Budget quarterly rule updates. Engage a tax consultant.

---

### U3 — Real-time Collaboration Necessity

| Priority | MEDIUM |
|---|---|
| **Type** | Technical |

**What we don't know**: Do users need real-time collaboration (multiple people editing the same fiscal period simultaneously)? The research recommends CRDTs (Yjs) but this adds significant complexity.

**How to resolve**: Ask target users during market validation. Default to "no" for Phase 1 — most SMBs have 1-2 finance users.

---

### U4 — Plugin Ecosystem Viability

| Priority | MEDIUM |
|---|---|
| **Type** | Business |

**What we don't know**: Will third-party developers build plugins for this platform? The marketplace model depends on developer adoption.

**How to resolve**: Build the core first. Attract developers with open-source core + clear SDK docs. Seed with 15-20 first-party plugins.

---

### U5 — NFS-e Municipal Coverage Priority

| Priority | MEDIUM |
|---|---|
| **Type** | Compliance |

**What we don't know**: Which 100 municipalities to prioritize for NFS-e support. The answer depends on target market geography.

**How to resolve**: Start with the top 20 cities by GDP (Sao Paulo, Rio, Belo Horizonte, Curitiba, etc.). Expand based on user demand.

---

### U6 — Rust Migration Timing

| Priority | MEDIUM |
|---|---|
| **Type** | Technical |

**What we don't know**: When to start migrating components to Rust per D-022. The AGENTS.md says "Cement in Rust" but the current codebase is 100% TypeScript/Python.

**How to resolve**: Build and validate in TypeScript/Python first. Migrate to Rust module-by-module after behavior is validated. The gateway and CLI are good first Rust candidates.

---

### U7 — Real-time Collaboration with Yjs

| Priority | LOW |
|---|---|
| **Type** | Technical |

**What we don't know**: Is Yjs overkill for financial data? The research says CRDTs + server-side invariant validation, but most SMBs don't need real-time collaboration.

**How to resolve**: Defer Yjs to Phase 4+. Use optimistic locking (version column) for Phase 1.

---

### U8 — Supabase vs Self-Hosted PostgreSQL

| Priority | MEDIUM |
|---|---|
| **Type** | Technical |

**What we don't know**: Should the platform use Supabase (managed) or self-hosted PostgreSQL? Supabase simplifies auth/storage but adds vendor lock-in. Self-hosted is more flexible but requires ops expertise.

**How to resolve**: Start with Supabase for speed. Design the data layer with a PostgreSQL adapter interface so self-hosting is possible later.

---

## Risk Heat Map

| | Impact L | Impact M | Impact H |
|---|---|---|---|
| **Prob H** | — | R2, R7, R8, R14 | R1, R3, R6, R11, R15, R16, R18, R21, R28, R29, B1-B5, U1, U2 |
| **Prob M** | R5 | R4, R10, R13, R17, R19, R25, R30 | R9, R12, R22, R24, R26, R27 |
| **Prob L** | — | R20 | R23 |

---

## Top 5 Risks and Mitigations (Summary)

1. **Compliance timeline uncertainty (R6, CBS/IBS tax reform)** — Probability: H, Impact: H. Mitigation: Build tax engine as rule-based config with effective dates, not hardcoded logic; defer PIS/COFINS/ICMS to Phase 2; engage tax consultant for rule validation.

2. **Event sourcing adoption without team expertise (R2)** — Probability: H, Impact: M. Mitigation: Prototype event sourcing for journal entries only (1-week timebox); fall back to traditional CRUD if no clear audit trail benefit; use Redis Streams for event bus.

3. **Plugin system complexity exceeding team capacity (R3)** — Probability: H, Impact: H. Mitigation: Start with database-driven module registry (enable/disable via config), not a full SDK; build lifecycle hooks in Phase 2; defer marketplace until 10+ modules stable.

4. **Existing data migration from SQLite to PostgreSQL (R21)** — Probability: H, Impact: H. Mitigation: Build new system first, migrate later; use content-hash idempotent imports; run old and new systems in parallel during transition; daily reconciliation reports.

5. **Brazilian compliance domain knowledge gap (R16)** — Probability: H, Impact: H. Mitigation: Engage licensed contador as consultant during compliance module development; use open-source SPED/NFe libraries as reference; validate against official Receita Federal validators; budget legal review before GA.

---

## Cross-Reference: Open Questions from Research Reports

| # | Open Question | Risk Link | Priority |
|---|---|---|---|
| 1 | Pricing final — test with real users | R11 | HIGH |
| 2 | AI roadmap — categorization as quick win | — | MEDIUM |
| 3 | Real-time collaboration — Yjs from start? | U3, U7 | LOW |
| 4 | Open-source % — how much vs proprietary | B3 | HIGH |
| 5 | Go-to-market — MEIs first or mid-size? | B2, R14 | HIGH |
| 6 | Multi-tenant — shared DB or dedicated? | B4 | HIGH |
| 7 | Event sourcing vs traditional — prototype needed | R2 | HIGH |
| 8 | NFS-e — prioritize top 100 municipalities | U5, R8 | MEDIUM |
| 9 | Transfer pricing module — out of scope | — | LOW |
| 10 | IFRS 17 insurance — deep implementation not covered | — | LOW |
| 11 | PgBouncer + RLS — verify compatibility | R4 | MEDIUM |
| 12 | Marketplace seed — which 15-20 plugins first | U4 | MEDIUM |

---

*This risk register should be reviewed monthly and updated as mitigations are implemented or new risks emerge.*
