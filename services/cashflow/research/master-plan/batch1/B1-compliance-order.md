# Compliance Implementation Order — L2 Cashflow

> Generated 2026-07-10 · Brazilian Fiscal + International Compliance · Effort: 140-195 days (28-39 weeks)

## Executive Summary

Compliance implementation follows a **progressive complexity model**: start with what every MEI/ME needs (basic CNPJ validation, Simples Nacional calculation, NFS-e for services), then add enterprise requirements (SPED, NFe, eSocial), and finally international standards (IFRS, LGPD/GDPR, SOX). Total effort: **140-195 days** across 5 phases.

---

## Phase 1: Foundation — MEI/ME Essentials (20-25 days)

### 1.1 CNPJ Validation — BrasilAPI Integration

| Aspect | Detail |
|--------|--------|
| **Effort** | 3-4 days |
| **Dependencies** | None (standalone) |
| **Risk** | Low |
| **What to build** | CNPJ modulus-11 validation algorithm + alphanumeric support (July 2026), BrasilAPI integration for real-time lookup (regime_tributario, QSA, CNAEs, situação_cadastral), CNPJ normalization (input/output formatting), batch validation endpoint |
| **MVP** | Client-side validation + single CNPJ lookup |
| **Full** | Batch validation, caching layer, webhook for status changes |
| **Key files** | `lib/cnpj.ts`, `lib/brasil-api.ts`, `app/api/cnpj/[cnpj]/route.ts` |

**Algorithm reference** (from REPORT-TECHNICAL.md §4.5):
```
v[1] = 5×c[1] + 4×c[2] + 3×c[3] + 2×c[4] + 9×c[5] + 8×c[6] + 7×c[7] + 6×c[8] + 5×c[9] + 4×c[10] + 3×c[11] + 2×c[12]
v[1] = 11 - (v[1] mod 11); if v[1] >= 10 then v[1] = 0

v[2] = 6×c[1] + 5×c[2] + 4×c[3] + 3×c[4] + 2×c[5] + 9×c[6] + 8×c[7] + 7×c[8] + 6×c[9] + 5×c[10] + 4×c[11] + 3×c[12] + 2×c[13]
v[2] = 11 - (v[2] mod 11); if v[2] >= 10 then v[2] = 0
```

### 1.2 Simples Nacional Tax Engine — MEI/ME First

| Aspect | Detail |
|--------|--------|
| **Effort** | 8-10 days |
| **Dependencies** | CNPJ validation (1.1) |
| **Risk** | Medium (annual table updates) |
| **What to build** | DAS MEI calculation (current: R$71.60/month services), Simples Nacional tables (Anexos I-V with faixas, alíquotas nominais, parcelas a deduzir), Fator R calculation (Folha/Receita Bruta ≥28% → Anexo III, <28% → Anexo V), regime_tributario detection from CNPJ lookup, tax calendar integration (DAS due dates) |
| **MVP** | MEI DAS + Simples Nacional Anexo V (services) |
| **Full** | All 5 annexes, Fator R auto-calculation, LC 123/2023 Reforma Tributária projection |
| **Key files** | `lib/tax.ts` (extend existing), `lib/simples-nacional.ts`, `lib/fator-r.ts` |

**Simples Nacional annexes** (from REPORT-TECHNICAL.md §4.7):
- **Anexo I**: Comércio (ICMS)
- **Anexo II**: Indústria (ICMS)
- **Anexo III**: Serviços (alíquotas menores com Fator R ≥28%)
- **Anexo IV**: Serviços (construção civil)
- **Anexo V**: Serviços (alíquotas maiores com Fator R <28%)

### 1.3 Basic NFS-e Integration — ABRASF Standard

| Aspect | Detail |
|--------|--------|
| **Effort** | 8-10 days |
| **Dependencies** | CNPJ validation (1.1), tax engine (1.2) |
| **Risk** | High (5,570 municipalities, each with variations) |
| **What to build** | ABRASF 2.03/2.04 XML schema, RPS (Recibo Provisório de Serviços) generation, NFS-e transmission via SOAP, municipal web service discovery, basic XML signing (SHA-256), first 3 cities: São Paulo (SEFAZ-SP), Rio de Janeiro, Belo Horizonte |
| **MVP** | São Paulo NFS-e only (largest market) |
| **Full** | 100+ municipalities, RPS→NFS-e conversion, batch transmission, error handling |
| **Key files** | `lib/nfs-e/`, `lib/nfs-e/sao-paulo.ts`, `lib/nfs-e/abrasyf-client.ts` |

**Municipal priority** (from REPORT-TECHNICAL.md §4.3):
| Priority | City | Standard | Notes |
|----------|------|----------|-------|
| 1 | São Paulo | ABRASF 2.03 | ISS 2-5% por CNAE, SEFAZ-SP |
| 2 | Rio de Janeiro | ABRASF 2.04 | RPS flow diferente |
| 3 | Belo Horizonte | ABRASF 2.03 | Regras específicas construção |
| 4-10 | Curitiba, Brasília, Salvador, Fortaleza, Manaus, Recife, Porto Alegre | ABRASF 2.02-2.04 | Cada uma com particularidades |

### 1.4 Tax Calendar & Due Dates

| Aspect | Detail |
|--------|--------|
| **Effort** | 1-2 days |
| **Dependencies** | Tax engine (1.2) |
| **Risk** | Low |
| **What to build** | DAS MEI due date (dia 20), Simples Nacional DAS (dia 15), LC 116/2003 ISS deadlines, fiscal year configuration |
| **MVP** | Static calendar with alerts |
| **Full** | Dynamic calendar with municipal/state variations |

**Phase 1 Total: 20-25 days**

---

## Phase 2: Enterprise Compliance — NFe + eSocial (45-55 days)

### 2.1 NFe Integration — SEFAZ SOAP Client

| Aspect | Detail |
|--------|--------|
| **Effort** | 20-25 days |
| **Dependencies** | CNPJ validation (1.1) |
| **Risk** | High (complex SOAP, XML signing, certificate management) |
| **What to build** | SEFAZ SOAP 1.2 client with X.509 mutual TLS, NFe 4.00 XML schema generation, digital certificate management (A1/A3), XML signing (SHA-256 + RSA-2048), chave de acesso generation (44 dígitos), authorization flow (NfeAutorizacao → NfeRetAutorizacao), status codes handling (100=autorizado, 204=duplicidade, etc.), cancellation and correction letter events |
| **MVP** | Single SEFAZ (SVRS) with basic authorization |
| **Full** | All 15 SEFAZ autorizadores, batch processing, retry logic, contingency mode |
| **Key files** | `lib/nfe/`, `lib/nfe/sefaz-client.ts`, `lib/nfe/xml-signer.ts`, `lib/nfe/certificate.ts`, `lib/nfe/autorizacao.ts` |

**SEFAZ autorizadores** (from REPORT-TECHNICAL.md §4.2):
- **SVAN**: Servidor Virtual Autorizador Nacional (Nacional)
- **SVRS**: Servidor Virtual Autorizador Regional (Sul/Sudeste)
- **SVC-AN/SVC-RS**: Serviço Virtual de Contingência
- **11 estaduais**: SP, MG, RS, PR, SC, RJ, ES, BA, PE, CE, AM

**Web services** (from REPORT-TECHNICAL.md §4.2):
```
NfeAutorizacao, NfeRetAutorizacao, NfeInutilizacao,
NfeConsultaProtocolo, NfeStatusServico, NfeConsulta,
RecepcaoEvento, NfeDistribuicaoDFe
```

### 2.2 Digital Certificate Management

| Aspect | Detail |
|--------|--------|
| **Effort** | 5-7 days |
| **Dependencies** | None (standalone) |
| **Risk** | Medium (security-critical) |
| **What to build** | Certificate upload (A1 .pfx/.p12 + A3 hardware token), certificate validation (expiry, chain, revocation), secure storage (HSM/cloud KMS integration), certificate rotation workflow, multi-certificate support per tenant |
| **MVP** | A1 certificate upload + basic validation |
| **Full** | A3 hardware token support, cloud HSM integration, automated renewal alerts |
| **Key files** | `lib/nfe/certificate.ts`, `lib/nfe/hsm.ts`, `app/api/certificates/route.ts` |

### 2.3 NFe XML Validation & Schema

| Aspect | Detail |
|--------|--------|
| **Effort** | 3-4 days |
| **Dependencies** | NFe integration (2.1) |
| **Risk** | Medium |
| **What to build** | XSD schema validation for NFe 4.00, business rule validation (item codes, tax calculations, address formats), error message mapping to human-readable descriptions |
| **MVP** | Basic schema validation |
| **Full** | Full business rule validation, custom validation rules |

### 2.4 eSocial Integration

| Aspect | Detail |
|--------|--------|
| **Effort** | 15-20 days |
| **Dependencies** | CNPJ validation (1.1), digital certificates (2.2) |
| **Risk** | High (complex event types, strict deadlines) |
| **What to build** | eSocial event generation (S-1200, S-1210, S-1299), digital certificate integration, DCTFWeb submission, XML schema validation, payroll data mapping, event sequencing, deadline management (prazo: último dia do mês seguinte) |
| **MVP** | S-1200 (remuneração) + S-1299 (fechamento) |
| **Full** | All event types, batch processing, DCTFWeb integration, error correction |
| **Key files** | `lib/esocial/`, `lib/esocial/event-generator.ts`, `lib/esocial/dctf-web.ts` |

**eSocial events** (from REPORT-TECHNICAL.md §4.4):
- **S-1200**: Remuneração do trabalhador (CPF, rubricas, valores)
- **S-1210**: Pagamentos (beneficiário, data, valor líquido, IRF)
- **S-1299**: Fechamento dos eventos periódicos (prazo: último dia do mês seguinte)
- **Layout v.S-1.3**: CNPJ alfanumérico produção 01/07/2026

### 2.5 ST/DIFAL Calculation

| Aspect | Detail |
|--------|--------|
| **Effort** | 4-5 days |
| **Dependencies** | NFe integration (2.1) |
| **Risk** | Medium |
| **What to build** | DIFAL calculation: `BC × (alíquota_interna - alíquota_interestadual)`, interestadual rates: 4% (Sul/Sudeste), 7% (demais → Sul/Sudeste), 12%, ICMS-ST calculation, aliquota tracking per state |
| **MVP** | Basic DIFAL calculation |
| **Full** | Full ST/DIFAL with state-specific rules |

**Phase 2 Total: 45-55 days**

---

## Phase 3: SPED Generation (30-40 days)

### 3.1 EFD-Contribuições — PIS/COFINS

| Aspect | Detail |
|--------|--------|
| **Effort** | 10-12 days |
| **Dependencies** | NFe integration (2.1), tax engine (1.2) |
| **Risk** | Medium |
| **What to build** | Pipe-delimited file generation, A100 (NF documents), A170 (items), M100/M200 (PIS crédito/consolidação), M500/M600 (COFINS crédito/consolidação), tax rate mapping: PIS não-cumulativo 1.65%, cumulativo 0.65%; COFINS não-cumulativo 7.6%, cumulativo 3.0% |
| **MVP** | Basic PIS/COFINS calculation + file generation |
| **Full** | Credit regime selection, non-cumulative optimization, audit trail |
| **Key files** | `lib/sped/efd-contribuicoes.ts`, `lib/sped/records/` |

### 3.2 EFD-ICMS IPI

| Aspect | Detail |
|--------|--------|
| **Effort** | 10-12 days |
| **Dependencies** | NFe integration (2.1), ST/DIFAL (2.5) |
| **Risk** | Medium-High (state-specific variations) |
| **What to build** | C100 (NF entrada/saída), C170 (itens), E110 (apuração ICMS), E200/E210 (ICMS-ST), E300 (DIFAL), E500/E520 (IPI), state-specific adjustments |
| **MVP** | Basic ICMS/IPI calculation + single state |
| **Full** | All states, ST/DIFAL integration, credit recovery |
| **Key files** | `lib/sped/efd-icms-ipi.ts`, `lib/sped/records/` |

### 3.3 ECD — Escrituração Contábil Digital

| Aspect | Detail |
|--------|--------|
| **Effort** | 8-10 days |
| **Dependencies** | EFD-Contribuições (3.1), EFD-ICMS IPI (3.2) |
| **Risk** | Medium |
| **What to build** | Bloco A (0000 abertura, 0150 participantes, 0500 plano de contas), Bloco C (1001, 1800 DRE), Bloco E (3001 razão, 3500 balanço), Bloco J (9900 registros, 9999 totalização), cross-validation with GL entries |
| **MVP** | Basic balance sheet generation |
| **Full** | Full trial balance, DRE, equity statement |
| **Key files** | `lib/sped/ecd.ts`, `lib/sped/records/` |

### 3.4 ECF — Escrituração Contábil Fiscal

| Aspect | Detail |
|--------|--------|
| **Effort** | 5-7 days |
| **Dependencies** | ECD (3.3) |
| **Risk** | Low-Medium |
| **What to build** | ECF file generation, LALUR (Livro de Apuração do Lucro Real), adjustments and additions, tax base calculation |
| **MVP** | Basic LALUR generation |
| **Full** | Full ECF with all registers |
| **Key files** | `lib/sped/ecf.ts` |

### 3.5 SPED Validation & Testing

| Aspect | Detail |
|--------|--------|
| **Effort** | 5-7 days |
| **Dependencies** | All SPED modules (3.1-3.4) |
| **Risk** | Medium |
| **What to build** | SEFAZ validation tools (SPEDValida, EFD-Contribuicoes validator), schema validation, business rule validation, test data generation, golden master tests |
| **MVP** | Basic schema validation |
| **Full** | Full SEFAZ validator integration, automated testing |
| **Key files** | `lib/sped/validator.ts`, `tests/sped/` |

**Phase 3 Total: 30-40 days**

---

## Phase 4: LGPD/GDPR + Data Protection (15-20 days)

### 4.1 LGPD Compliance — Brazil Data Protection

| Aspect | Detail |
|--------|--------|
| **Effort** | 8-10 days |
| **Dependencies** | None (standalone) |
| **Risk** | Medium-High (legal requirements) |
| **What to build** | Data classification (sensitive/personal/financial), consent management (LGPD Art. 7), data subject rights (access, correction, deletion, portability), data processing records (LGPD Art. 37), privacy policy enforcement, data retention policies, DPO (Data Protection Officer) workflow |
| **MVP** | Basic consent + data subject rights |
| **Full** | Full LGPD compliance with automated workflows |
| **Key files** | `lib/lgpd/`, `lib/lgpd/consent.ts`, `lib/lgpd/data-subject.ts` |

### 4.2 GDPR Compliance — International

| Aspect | Detail |
|--------|--------|
| **Effort** | 5-7 days |
| **Dependencies** | LGPD (4.1) |
| **Risk** | Medium |
| **What to build** | GDPR-specific requirements (Lawful Basis, Data Minimization, Purpose Limitation), cross-border data transfer mechanisms, DPIA (Data Protection Impact Assessment), breach notification workflow (72 hours), cookie consent management |
| **MVP** | Basic GDPR alignment with LGPD |
| **Full** | Full GDPR compliance for EU customers |
| **Key files** | `lib/gdpr/`, `lib/gdpr/breach-notification.ts` |

### 4.3 Data Encryption & Security

| Aspect | Detail |
|--------|--------|
| **Effort** | 3-4 days |
| **Dependencies** | LGPD (4.1) |
| **Risk** | Medium |
| **What to build** | Data encryption at rest (AES-256), data encryption in transit (TLS 1.3), key management (HSM/cloud KMS), access logging for sensitive data, audit trail for data access |
| **MVP** | Basic encryption + access logging |
| **Full** | HSM integration, automated key rotation |
| **Key files** | `lib/security/encryption.ts`, `lib/security/key-management.ts` |

### 4.4 SOX Compliance — Financial Controls

| Aspect | Detail |
|--------|--------|
| **Effort** | 3-5 days |
| **Dependencies** | Audit trail (existing), RBAC (existing) |
| **Risk** | Low-Medium (building on existing) |
| **What to build** | Segregation of duties enforcement, change management controls, financial reporting controls, audit trail enhancement, automated testing of controls |
| **MVP** | Basic control documentation |
| **Full** | Automated control testing + reporting |
| **Key files** | `lib/compliance/sox.ts`, `lib/compliance/controls.ts` |

**Phase 4 Total: 15-20 days**

---

## Phase 5: IFRS + Multi-GAAP (30-55 days)

### 5.1 IFRS 15 — Revenue from Contracts

| Aspect | Detail |
|--------|--------|
| **Effort** | 12-15 days |
| **Dependencies** | Core ledger (existing), event sourcing (existing) |
| **Risk** | High (complex recognition rules) |
| **What to build** | 5-stage revenue recognition (identify contract → identify obligations → estimate price → allocate → recognize), SSP (Standalone Selling Price) calculation, deferred revenue tracking, contract modification accounting, point-in-time vs over-time recognition |
| **MVP** | Basic subscription revenue recognition |
| **Full** | Complex multi-element arrangements |
| **Key files** | `lib/ifrs/ifrs15.ts`, `lib/ifrs/revenue-recognition.ts` |

### 5.2 Multi-GAAP Architecture

| Aspect | Detail |
|--------|--------|
| **Effort** | 10-15 days |
| **Dependencies** | IFRS 15 (5.1), base ledger |
| **Risk** | High (architectural complexity) |
| **What to build** | Base ledger → Adjustment layers → Reporting views architecture, COA universal with mapping tables (SKR03/04, PCG, ECF/CTB, US GAAP), standard-specific adjustments, period-end close workflow, consolidation |
| **MVP** | IFRS + Brazilian GAAP (ECF/CTB) |
| **Full** | IFRS + US GAAP + UK GAAP + 10+ others |
| **Key files** | `lib/multi-gaap/`, `lib/multi-gaap/adjustment-layer.ts`, `lib/multi-gaap/mapping.ts` |

### 5.3 IFRS 16 — Leases

| Aspect | Detail |
|--------|--------|
| **Effort** | 5-7 days |
| **Dependencies** | Multi-GAAP (5.2) |
| **Risk** | Medium |
| **What to build** | Right-of-use asset calculation, lease liability (PV of payments), short-term/low-value exceptions, modification accounting |
| **MVP** | Basic lease accounting |
| **Full** | Complex lease modifications, subleases |
| **Key files** | `lib/ifrs/ifrs16.ts` |

### 5.4 IFRS 18 — 2027 Preparation

| Aspect | Detail |
|--------|--------|
| **Effort** | 3-5 days |
| **Dependencies** | Multi-GAAP (5.2) |
| **Risk** | Low (future requirement) |
| **What to build** | Mandatory Performance Measures (MPMs) framework, disaggregation schema, early adoption support |
| **MVP** | Schema ready for IFRS 18 |
| **Full** | Full IFRS 18 reporting |
| **Key files** | `lib/ifrs/ifrs18.ts` |

### 5.5 IFRS 17 — Insurance Contracts (Optional)

| Aspect | Detail |
|--------|--------|
| **Effort** | 5-8 days |
| **Dependencies** | Multi-GAAP (5.2) |
| **Risk** | High (very complex) |
| **What to build** | GMM/PAA/VFA measurement models, Contractual Service Margin (CSM), premium allocation |
| **MVP** | Skip unless targeting insurance industry |
| **Full** | Full IFRS 17 implementation |
| **Key files** | `lib/ifrs/ifrs17.ts` |

### 5.6 Compliance Testing & Validation

| Aspect | Detail |
|--------|--------|
| **Effort** | 3-5 days |
| **Dependencies** | All compliance modules |
| **Risk** | Medium |
| **What to build** | Property-based testing for tax calculations, golden master tests for SPED files, schema validation for NFe/NFS-e XML, contract tests for SEFAZ/eSocial APIs, compliance report generation |
| **MVP** | Basic validation tests |
| **Full** | Full compliance test suite |
| **Key files** | `tests/compliance/`, `tests/tax/`, `tests/sped/` |

**Phase 5 Total: 30-55 days**

---

## Effort Summary

| Phase | Scope | Days | Weeks | Dependencies |
|-------|-------|------|-------|--------------|
| **Phase 1** | MEI/ME Essentials (CNPJ, Simples, NFS-e, Calendar) | 20-25 | 4-5 | None |
| **Phase 2** | Enterprise (NFe, eSocial, Certificates, ST/DIFAL) | 45-55 | 9-11 | Phase 1 |
| **Phase 3** | SPED Generation (EFD-Contribuições, EFD-ICMS, ECD, ECF) | 30-40 | 6-8 | Phase 2 |
| **Phase 4** | LGPD/GDPR + SOX + Data Protection | 15-20 | 3-4 | None (parallel) |
| **Phase 5** | IFRS + Multi-GAAP + Testing | 30-55 | 6-11 | Phase 3 |
| **Total** | — | **140-195** | **28-39** | — |

---

## Risk Matrix

| Component | Risk | Mitigation |
|-----------|------|------------|
| NFe SEFAZ client | High (SOAP complexity) | Start with SVRS only, add states incrementally |
| NFS-e municipal | High (5,570 cities) | Start with São Paulo, add top 10 cities first |
| eSocial events | High (strict deadlines) | MVP with S-1200/S-1299 only |
| SPED validation | Medium | Use SEFAZ validation tools, golden master tests |
| LGPD/GDPR | Medium-High | Legal review required, build framework first |
| IFRS recognition | High | Start with subscription revenue, add complexity |
| Simples Nacional tables | Medium | Annual update process, version control |

---

## Decision Record

### D-COMP-001: Start with MEI/ME, not enterprise
**Decision**: Phase 1 targets MEI/ME essentials (CNPJ, Simples, basic NFS-e) before enterprise features (NFe, eSocial, SPED).
**Rationale**: MEI/ME is the largest market segment in Brazil (19M+ MEIs, 6M+ MEs). Faster time-to-market, lower complexity, immediate value.
**Trade-off**: Delays enterprise customer acquisition but validates core tax engine with simpler cases first.

### D-COMP-002: NFS-e first, NFe second
**Decision**: NFS-e (services) before NFe (products/goods).
**Rationale**: L2's primary market is services (SaaS, consulting, education). NFS-e is simpler (fewer item types, no inventory tracking).
**Trade-off**: Delays e-commerce/retail customers but aligns with current target market.

### D-COMP-003: São Paulo first for NFS-e
**Decision**: Implement São Paulo NFS-e before other municipalities.
**Rationale**: Largest market (12M+ population), well-documented ABRASF 2.03, SEFAZ-SP is the most stable web service.
**Trade-off**: Limited to SP initially but establishes patterns for other cities.

### D-COMP-004: LGPD/GDPR parallel to compliance
**Decision**: Run LGPD/GDPR (Phase 4) in parallel with SPED (Phase 3).
**Rationale**: LGPD is a legal requirement independent of fiscal compliance. Can be developed in parallel without dependencies.
**Trade-off**: Requires parallel team focus but doesn't delay fiscal compliance.

### D-COMP-005: IFRS 15 before Multi-GAAP
**Decision**: Implement IFRS 15 revenue recognition before full Multi-GAAP architecture.
**Rationale**: IFRS 15 is the most commonly required international standard for SaaS businesses. Validates the adjustment layer pattern before expanding.
**Trade-off**: Delays full Multi-GAAP but de-risks the architecture with a real use case.

---

## MVP Definition

### Minimum Viable Compliance (30-40 days)
- CNPJ validation + BrasilAPI integration
- MEI DAS calculation
- Simples Nacional Anexo V (services)
- São Paulo NFS-e (basic)
- Basic LGPD consent management
- Core compliance tests

### Full Compliance (140-195 days)
- All 5 SPED file types (ECD, ECF, EFD-Contribuições, EFD-ICMS IPI)
- NFe 4.00 with all SEFAZ autorizadores
- NFS-e for top 100 municipalities
- eSocial all event types
- Full LGPD/GDPR compliance
- IFRS 15/16/18 + Multi-GAAP
- SOX compliance controls
- Full compliance test suite

---

## Key Dependencies

```
CNPJ Validation (1.1)
  ├→ Simples Nacional (1.2)
  │   ├→ NFS-e (1.3)
  │   └→ Tax Calendar (1.4)
  ├→ NFe Integration (2.1)
  │   ├→ Digital Certificates (2.2)
  │   ├→ NFe Validation (2.3)
  │   ├→ ST/DIFAL (2.5)
  │   │   └→ EFD-ICMS IPI (3.2)
  │   └→ EFD-Contribuições (3.1)
  │       └→ ECD (3.3)
  │           └→ ECF (3.4)
  └→ eSocial (2.4)

LGPD/GDPR (4.1)
  ├→ GDPR (4.2)
  ├→ Data Encryption (4.3)
  └→ SOX (4.4)

IFRS 15 (5.1)
  └→ Multi-GAAP (5.2)
      ├→ IFRS 16 (5.3)
      ├→ IFRS 18 (5.4)
      └→ IFRS 17 (5.5)
```

---

## Success Criteria

| Phase | Success Metric |
|-------|----------------|
| Phase 1 | MEI can calculate DAS, validate CNPJ, generate basic NFS-e for SP |
| Phase 2 | Enterprise can issue NFe, comply with eSocial, calculate ST/DIFAL |
| Phase 3 | All SPED files generated and validated by SEFAZ tools |
| Phase 4 | LGPD consent working, data subject rights implemented, SOX controls documented |
| Phase 5 | IFRS 15 revenue recognition working, Multi-GAAP reports generating |

---

## Open Questions

1. **SEFAZ testing environment**: Do we have access to SVRS homologação environment for NFe testing?
2. **Digital certificate procurement**: Who provides A1/A3 certificates for development and production?
3. **eSocial producer**: Are we targeting eSocial Produção or Homologação first?
4. **Municipal partnership**: Any partnership with São Paulo SEFAZ-SP for NFS-e development?
5. **Legal review**: When to engage legal team for LGPD/GDPR compliance review?
6. **IFRS 17**: Is insurance industry in scope for L2 Cashflow MVP?

---

## Appendix: Reference Documents

- REPORT-TECHNICAL.md §4.1-4.8: Brazilian compliance technical specs
- REPORT-ACCOUNTING-SAAS-LOCALIZATION.md §1: IFRS/ASC implementation
- REPORT-ACCOUNTING-SAAS-LOCALIZATION.md §5: Marketplace Brazil requirements
- lib/tax.ts: Current MEI tax calculation (to be extended)
