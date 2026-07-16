# Research Brief: Modular Cashflow for Any Business

## Question
What modules and features does a modular cashflow system need to cover "absolutely everything imaginable for any business" — with multi-selection, easy customization, and full coverage of all business types?

## Context
The L2 Cashflow is currently a FinOps B2B platform for AI operations (Next.js 16 + SQLite/Supabase). The user wants to evolve it into a **universal modular financial system** that can be configured for ANY business type via an initial setup wizard. The system must support:
- Multi-selection of modules during setup
- Easy customization of each module
- Coverage of ALL imaginable business scenarios
- Brazilian market requirements (MEI, Simples Nacional, SPED, etc.)
- International adaptability

## Scope boundaries
- **IN**: All financial management modules, industry-specific features, automation patterns, integration points, regulatory requirements, UX/configurability patterns
- **OUT**: Non-financial modules (CRM beyond basic, HR/payroll, inventory management as separate system), specific code implementation details

## Assumptions
- Target market: Brazilian businesses (MEI, LTDA, SA) with international adaptability
- Stack: Next.js + SQLite/Supabase (existing)
- The system should be installable/configurable by a non-technical user
- Modules should be independently activatable

## Angles (research plan)

### F1: Universal financial management modules
What are ALL the core financial modules any business needs? Cover: accounts payable, accounts receivable, cash management, general ledger, financial reporting, budgeting, tax management, multi-currency, inter-company transactions. Look at what QuickBooks, Xero, FreshBooks, Nubank PJ, and similar systems offer.

### F2: Industry-specific features by business type
What features are specific to: retail/e-commerce, services/consulting, SaaS/subscriptions, manufacturing, restaurants/food, construction, real estate, healthcare, education, agriculture, marketplace/platform? What unique financial workflows does each need?

### F3: Brazilian regulatory and tax requirements
What are ALL the Brazilian tax/regulatory requirements for businesses? MEI limits, Simples Nacional tables, SPED (ECD/ECF/EFD-Contribuições), NF-e/NFC-e integration, Pix, boleto, CNAB 240/400, DAS/DARF, ICMS/ISS/IRPJ/CSLL/PIS/COFINS. What systems must a financial tool have to be compliant?

### F4: Automation, notifications, and integration patterns
What automations and integrations does a modern financial system need? Recurring billing, payment reminders, bank reconciliation, accounting software integration (Domínio, Tiny, Bling), email/WhatsApp notifications, API webhooks, import/export (OFX, CSV, CNAB), multi-gateway payment processing.

### F5: Modular architecture patterns for configurable financial systems
How do successful modular financial systems handle: module discovery, dependency management, lazy loading, configuration persistence, schema migrations per module, on-demand activation/deactivation, version compatibility between modules, and user permission per module? Look at WordPress plugins, ERPNext modules, Odoo modules as reference.

### F6: Multi-company, holding, and franchise patterns
What financial features are needed for: holding companies, multi-entity consolidation, inter-company transfers, franchise operations, white-label reselling, multi-tenant SaaS platforms? How do these affect the module architecture?

## Depth mode
**deep** — 5-8 sub-agents, 2 follow-up rounds, 25+ sources target
