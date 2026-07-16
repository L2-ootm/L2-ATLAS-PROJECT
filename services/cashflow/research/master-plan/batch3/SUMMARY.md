# Batch 3 Summary: Compliance & Integrations

## Key Findings

### Tax Engine (B3-tax-engine.md)
- 40-55 days, hybrid architecture (calculation modules + config-driven rates)
- Simples Nacional progressive rate applies to ENTIRE RBT12 (common mistake: marginal)
- Decimal.js non-negotiable for all tax calculations
- CBS/IBS transition: additive parallel calculation for 7+ years

### NFe + NFS-e (B3-nfe-nfse.md)
- 91 days: NFS-e 40d, NFe 35d, Testing 16d
- NFS-e first (services-first market, São Paulo first)
- Pluggable municipality architecture for NFS-e variations
- EPEC contingency mode for SEFAZ downtime

### SPED Generation (B3-sped-generation.md)
- 36-46 days across 4 SPED types
- Cascading dependencies: ECD depends on EFD-Contribuições + EFD-ICMS/IPI
- Three-layer design: Record → Block → File with pluggable extractors
- 5-layer validation before SEFAZ validator run

### eSocial Integration (B3-esocial.md)
- MVP: only 3 events (S-1200 + S-1299 + Certificate)
- Layout v.S-1.3 production 01/07/2026
- DCTFWeb auto-generated — no separate filing logic
- Payroll adapter pattern for parallel development

### Payment Gateways (B3-payment-gateways.md)
- 55 dev-days, 4 providers (Asaas, PagSeguro, Mercado Pago, Stripe)
- Stripe has lowest Pix fee (0.8% vs 0.99%)
- Provider adapter pattern with common interface
- Webhook idempotency by provider-event-ID

### Banking Integration (B3-banking-integration.md)
- Belvo for MVP (3-4 weeks), Open Finance deferred to Phase 2
- All formats normalize into single `bank_transactions` table
- Duplicate detection keyed on (tenant, account, source_id, format)
- OFB consent lifecycle requires 30-day re-consent prompts

## Batch 3 Subtotal
- Tax Engine: 40-55 days
- NFe + NFS-e: 91 days
- SPED: 36-46 days
- eSocial: ~30 days (estimated from 3 events)
- Payment Gateways: 55 days
- Banking: ~40 days (estimated)
- **Batch 3 subtotal: ~292-317 days (~58-63 weeks)**
