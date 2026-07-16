# Modular Cashflow Universal — Relatório: Segurança, Performance, DevOps, Migração, Testing, Mobile

> Generated 2026-07-09 · depth: deep · 18 findings files totais · workspace: research/modular-cashflow/

## Executive Summary

**Segurança**: Envelope encryption (DEK/KEK) com AES-256-GCM. OAuth 2.0 + PKCE para auth. RBAC + RLS para multi-tenancy. Immutable audit trail com hash-chaining. PCI DSS scope reduction via tokenização (SAQ D → SAQ A). LGPD/GDPR: retention 5-7 anos mínimo para dados financeiros.

**Performance**: Composite indexes com INCLUDE para index-only scans (60-80% I/O reduction). Materialized views para relatórios (2-5s → 50-200ms). Cache TTL: session 30min, balances 5min, P&L 15min. PgBouncer transaction pooling (5-10x mais conexões). Partition pruning para tabelas grandes.

**DevOps**: Vercel ISR (5min revalidate) para dashboards. Prisma migrate deploy com advisory lock. Unleash OSS para feature flags per-tenant. Blue-green + feature flags (não canary) para deploy financeiro. RPO <1h via WAL archiving. RTO <4h com restore automatizado.

**Migração**: OFX/QFX via ofxtools (Python, zero deps). CNAB 240/400 fixed-width com header/transaction/trailer. QuickBooks IIF (tab-delimited) + QBO (XML). Column mapping configurável. Idempotent imports via content hashes. Post-migration: reconciliation reports + audit log.

**Testing**: Decimal everywhere (nunca float). Property-based testing (hypothesis) para invariantes. Golden master snapshots para relatórios. Time-travel testing (freezegun) para períodos fiscais. Contract testing (Pact) entre módulos. SPED/NFe schema validation automatizada em CI.

**Mobile/PWA**: Serwist (substituto do next-pwa deprecado). Hybrid caching: CacheFirst/static, NetworkFirst/dashboard, StaleWhileRevalidate/transactions, NetworkOnly/payments. Dexie.js para IndexedDB. WebAuthn para biometria em PWA. CRDTs overkill — usar event sourcing + outbox.

---

## 1. Segurança Profunda

### 1.1 Envelope Encryption (DEK/KEK)

```
Data → encrypt with DEK (random 256-bit) → ciphertext + encrypted_DEK
KEK (in HSM/Vault) → encrypts DEK → encrypted_DEK stored alongside ciphertext
```

- DEK: gerada por registro ou por coluna para dados de alta sensibilidade
- KEK: nunca sai do HSM/vault (AWS KMS, HashiCorp Vault, Azure Key Vault)
- Rotacionamento: KEK a cada 90 dias, DEK a cada 30 dias ou por registro
- **Resultado**: breach do banco sozinho não expõe dados — atacante precisa do vault

### 1.2 Cipher & Transport

- **At rest**: AES-256-GCM (authenticated encryption — confidencialidade + integridade)
- **In transit**: TLS 1.3 mínimo, mTLS para service-to-service
- **Headers**: HSTS `max-age=31536000; includeSubDomains`
- **Nunca**: ECB mode, SSL, TLS 1.0/1.1, 3DES, RC4

### 1.3 Authentication

- **OAuth 2.0 + PKCE** para web/mobile (previne authorization code interception)
- **JWT**: expiry 5-15 min, RS256/ES256, tenant_id no claim
- **Refresh tokens**: opaque, 30-90 dias, rotacionados no uso, httpOnly cookies
- **API keys**: scoped, rotacionadas a cada 90 dias, hasheadas no storage

### 1.4 Authorization

- **RBAC**: admin, accountant, viewer, auditor, ap_clerk, ar_clerk
- **ABAC**: condiciones por horário, IP, valor da transação
- **RLS**: database-level tenant isolation (PostgreSQL `SET app.tenant_id`)
- **Separation of duties**: quem inicia não aprova (dual-control)

### 1.5 PCI DSS

- **Tokenização** via Stripe/Adyen: scope reduction de SAQ D (300+ controles) para SAQ A (~20-30)
- Se processa cartão diretamente: SAQ D com req 1-12 (network, access, data protection, monitoring)

### 1.6 Fraud Detection

- Velocity checks: "mesmo usuário, 5 transações em 1 minuto"
- Duplicate detection: content hash + idempotency key
- Anomaly detection: desvio padrão em valores históricos
- Amount threshold alerts: transações > X precisam de aprovação

### 1.7 Audit Trail Imutável

```sql
CREATE TABLE audit_log (
    entry_id UUID PRIMARY KEY,
    previous_entry_hash TEXT NOT NULL,  -- hash-chaining
    current_entry_hash TEXT NOT NULL,
    user_id UUID NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id UUID,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

- Hash-chaining: `current_hash = SHA256(previous_hash + entry_data)`
- Qualquer alteração posterior quebra a cadeia — tamper-evident
- Retenção: 5-7 anos mínimo (regulatório), 10+ para SOX

### 1.8 LGPD/GDPR

- Dados financeiros têm retention mínima regulatória (5-7 anos)
- Right to deletion: cascade para primary DB, replicas, backups, search indexes
- Exceção: dados de transações financeiras não podem ser deletados por regulamentação
- Data minimization: coletar apenas o necessário para a função contábil

---

## 2. Performance & Scaling

### 2.1 Indexação

```sql
-- Covering index para balance sheet (index-only scan)
CREATE INDEX idx_je_income_expense 
ON journal_entries (account_type, posting_date)
INCLUDE (debit_amount, credit_amount, department_id)
WHERE account_type IN ('REVENUE', 'EXPENSE');

-- Partial index para entries unreconciled (subconjunto pequeno)
CREATE INDEX idx_unreconciled 
ON journal_entries (account_id, posting_date)
WHERE reconciliation_status = 'UNRECONCILED';

-- GIN para JSONB metadata
CREATE INDEX idx_je_metadata ON journal_entries USING GIN (metadata jsonb_path_ops);
```

**Impacto**: Partial indexes reduzem tamanho 60-80%. Covering indexes eliminam table lookups.

### 2.2 Materialized Views

```sql
-- Trial balance (refresh hourly)
CREATE MATERIALIZED VIEW mv_trial_balance AS
SELECT account_id, account_code, account_type,
    SUM(CASE WHEN debit > 0 THEN debit ELSE 0 END) as total_debits,
    SUM(CASE WHEN credit > 0 THEN credit ELSE 0 END) as total_credits
FROM journal_entry_lines jel
JOIN journal_entries je ON jel.je_id = je.je_id
WHERE je.is_posted = true
GROUP BY account_id, account_code, account_type;
```

**Impacto**: Queries de 2-5s → 50-200ms para relatórios complexos.

### 2.3 Cache TTLs

| Dado | TTL | Rationale |
|---|---|---|
| Session | 30min | Security standard |
| Account balances | 5min | Near-real-time |
| Trial balance | 10min | Hourly refresh |
| P&L report | 15min | Periodic snapshot |
| Balance sheet | 30min | Less volatile |
| Chart of accounts | 1h | Rarely changes |

### 2.4 Connection Pooling

- **PgBouncer** transaction pooling: 5-10x mais conexões com mesmo database
- Pool size: `min=5, max=20` por instância de aplicação
- **Atenção**: RLS + PgBouncer requer `SET app.tenant_id` por transaction, não por connection

### 2.5 Partitioning

```sql
-- Time-based partitioning para journal_entries
CREATE TABLE journal_entries (
    ...
) PARTITION BY RANGE (entry_date);

CREATE TABLE journal_entries_2026_q1 PARTITION OF journal_entries
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');
```

- Partition pruning elimina partições irrelevantes automaticamente
- Partições antigas podem ser arquivadas (detach + tablespace frio)

### 2.6 Bulk Operations

- **COPY command**: 50.000-100.000 rows/sec vs 500 rows/sec para INSERT individual
- **Batch journal entries**: processar em chunks de 1.000 linhas
- **Async processing**: Bull/BullMQ para imports grandes, dead letter queue para falhas

---

## 3. Deployment & DevOps

### 3.1 Vercel + Next.js

- **ISR** (5min revalidate) para dashboards — não para transações real-time
- **Preview deployments**: auto-criados em PRs, URL única por branch
- **Custom environments**: staging, QA com DATABASE_URL separado
- **Fluid compute**: reduz cold starts para dashboards com bursty traffic

### 3.2 Database Migrations

- **Nunca** `migrate dev` em produção — usar `migrate deploy`
- **Advisory lock** com timeout 10s para prevenir migrações concorrentes
- **Expand-contract pattern**: adicionar colunas → migrar dados → remover colunas antigas
- **CREATE INDEX CONCURRENTLY**: não bloqueia reads durante criação de índice
- **pg_repack**: reorganiza tabelas após migrações grandes sem locks pesados

### 3.3 Feature Flags

**Unleash OSS** com context fields customizados:
```json
{
  "contextField": "tenantId",
  "operator": "IN",
  "values": ["tenant-abc-123"]
}
```

**Alternativa lightweight** (database-driven):
```sql
CREATE TABLE tenant_feature_flags (
    tenant_id UUID REFERENCES tenants(id),
    feature_key TEXT NOT NULL,
    enabled BOOLEAN DEFAULT false,
    config JSONB DEFAULT '{}',
    PRIMARY KEY (tenant_id, feature_key)
);
```

### 3.4 Deploy Strategy

- **Blue-green + feature flags** (não canary) — financeiro exige atomicidade
- Rollback: desligar feature flag, não redeploy
- Canary é arriscado para dados financeiros (transações parciais = estado inconsistente)

### 3.5 Backup & DR

| Metrica | Target | Implementação |
|---|---|---|
| **RPO** | <1 hora | WAL archiving a cada 5min + pg_basebackup diário |
| **RTO** | <4 horas | Scripts automatizados de restore + testes periódicos |
| **Retention** | 30 dias | Backups diários, semanais, mensais |
| **Point-in-time recovery** | Até 30 dias | WAL segmentos preservados |

### 3.6 Observabilidade

- **Structured logging**: JSON com tenant_id, user_id, action, entity
- **OpenTelemetry**: distributed tracing para requests cross-module
- **Métricas customizadas**: entries/second, query latency p99, cache hit rate
- **Alertas**: error rate >1%, p99 latency >500ms, disk usage >80%

---

## 4. Data Migration

### 4.1 OFX Import

```
ofxtools (Python, GPL-3.0, zero deps) — parser abrangente OFXv1/v2
Campos: payee, type, date, amount, FITID (unique ID), memo, sic, mcc
Account types: Bank, CreditCard, Investment
```

### 4.2 CNAB 240/400

- **Fixed-width** 240 caracteres por linha
- Records: header (01), transações (01-09), trailer (01-09)
- Encoding: ASCII ou EBCDIC (varia por banco)
- Posições fixas por campo — parsing posicional

### 4.3 QuickBooks

- **IIF**: tab-delimited, record types TRNS/SPL/ENDTRNS (legacy Desktop)
- **QBO XML**: formato Online, campos padronizados

### 4.4 Xero

- **CSV export**: colunas padronizadas, encoding UTF-8
- **Mapping**: QuickBooks account numbers → custom COA codes

### 4.5 Import Idempotency

```sql
-- Content hash para dedup
CREATE TABLE import_hashes (
    file_hash TEXT PRIMARY KEY,
    source_system TEXT,
    imported_at TIMESTAMPTZ,
    record_count INTEGER
);

-- Idempotent insert
INSERT INTO journal_entries (...)
SELECT ... FROM staging_entries
WHERE content_hash NOT IN (SELECT content_hash FROM import_hashes);
```

### 4.6 Post-Migration Verification

1. **Reconciliation report**: debits = credits after import
2. **Balance comparison**: opening balances match source system
3. **Record count**: source count = target count
4. **Audit log**: timestamp, source, target, file hash, errors

---

## 5. Testing

### 5.1 Regra Inegociável: Decimal Everywhere

```python
from decimal import Decimal, ROUND_HALF_EVEN
getcontext().prec = 10
getcontext().rounding = ROUND_HALF_EVEN  # banker's rounding
```

- **Nunca** `float` para valores financeiros
- `NUMERIC(18,6)` no banco, `Decimal` no código

### 5.2 Property-Based Testing

```python
from hypothesis import given, strategies as st

@given(st.lists(st.decimals(min_value=0, max_value=1000000), min_size=2))
def test_journal_entry_always_balances(amounts):
    """Para qualquer lista de valores, debit == credit."""
    lines = [JournalLine(debit=a, credit=Decimal(0)) for a in amounts[:-1]]
    lines.append(JournalLine(debit=Decimal(0), credit=sum(amounts[:-1])))
    entry = JournalEntry(lines=lines)
    assert entry.total_debit == entry.total_credit
```

- Um único `@given` cobre 200+ cenários
- Invariantes: debits == credits, balances reconcile, no negative balances in assets

### 5.3 Golden Master Testing

```python
def test_income_statement_snapshot():
    report = generate_income_statement(tenant_id="test", period="2026-01")
    assert report == snapshot("income_statement_2026_01")
    # Se o snapshot mudar → diff é a review
```

- Snapshots são especificações executáveis
- Diffs de snapshot SÃO o code review para mudanças de cálculo

### 5.4 Time-Travel Testing

```python
from freezegun import freeze_time

@freeze_time("2026-01-31 23:59:59")
def test_period_closing():
    """Fechar período fiscal no último dia."""
    close_period("2026-01")
    assert get_period_status("2026-01") == "closed"

@freeze_time("2026-02-01 00:00:01")
def test_cannot_modify_closed_period():
    """Não permite modificar período fechado."""
    with pytest.raises(PeriodClosedError):
        create_journal_entry(date="2026-01-15", ...)
```

### 5.5 Contract Testing (Pact)

```typescript
// Invoicing module publishes
const invoiceEventSchema = {
  event_type: "invoice.paid",
  data: { invoice_id: "string", amount: "number", currency: "string" }
};

// Ledger module consumes
const ledgerConsumerPact = new ConsumerUILDER()
  .hasPactWith('ledger-provider')
  .given('invoice paid')
  .uponReceiving('an invoice.paid event')
  .withRequest({ method: 'POST', path: '/events', body: invoiceEventSchema })
  .willRespondWith({ status: 201 });
```

### 5.6 Coverage Targets

| Área | Target |
|---|---|
| Cálculos financeiros | 100% line coverage |
| Módulos core | 95%+ branch coverage |
| Property-based | 200+ exemplos por invariante |
| Regression | 1000+ cenários de regressão |
| Compliance | SPED XSD + NFe schema validados em CI |

### 5.7 Compliance Testing Automatizado

```bash
# SPED file validation
python -m sped_validator --file EFD_2026_01.txt --schema EFD_v016.xsd

# NFe schema validation
xmllint --schema nfe_v400.xsd nfe_example.xml --noout
```

- Validação de schema automatizada no CI, não manual antes de release
- Snapshot tests para output SPED (garante que mudanças de código não quebram formato)

---

## 6. Mobile & PWA

### 6.1 Serwist (Substituto do next-pwa)

```bash
npm install serwist
```

```js
// next.config.js
const { withSerwist } = require('@serwist/next');
module.exports = withSerwist({
  swSrc: 'app/sw.ts',
  swDest: 'public/sw.js',
  cacheOnFrontEndNav: true,
  reloadOnOnline: true,
});
```

### 6.2 Hybrid Caching Strategy

| Recurso | Strategy | Rationale |
|---|---|---|
| Static assets (JS/CSS/fonts) | CacheFirst | Versioned, nunca muda entre deploys |
| Dashboard data (KPIs, balances) | NetworkFirst (3s timeout) | Dados frescos preferidos, cache fallback |
| Transaction history | StaleWhileRevalidate | Mostrar cache imediatamente, refresh background |
| Payment submissions | NetworkOnly | Nunca cachear POST sensíveis |
| Invoice PDFs | CacheFirst + expiration | Arquivos grandes, cache após primeiro fetch |
| User preferences | CacheOnly | Local-first, sync separado |

### 6.3 IndexedDB com Dexie.js

```typescript
const db = new Dexie('CashflowDB');
db.version(1).stores({
  transactions: '++id, accountId, date, amount, &fitid',
  accounts: '++id, code, name, type',
  syncQueue: '++id, action, payload, timestamp'
});
```

- Compound indexes para queries financeiras
- `syncVersion` field para conflict detection
- Sync queue para operações offline → online

### 6.4 Biometria em PWA

- **WebAuthn API**: Face ID / fingerprint funciona em PWAs
- Não precisa de app nativo para autenticação biométrica
- Fallback: PIN/password para dispositivos sem biometria

### 6.5 Sync Offline → Online

```
1. Usuário cria transação offline → salva em IndexedDB + syncQueue
2. Service worker detecta connection → envia syncQueue para servidor
3. Servidor processa com idempotency key
4. Resposta atualiza IndexedDB com server-side ID
5. Conflitos: last-write-wins com conflict detection (mostrar ao usuário)
```

### 6.6 Limitações do PWA

- **Sem jailbreak/root detection** → mitigar com server-side risk scoring
- **Sem push notifications nativas** → usar Web Push API (suportado em Chrome, Firefox, Edge)
- **Offline payment submission** → Background Sync queue, não processamento offline real

---

## 7. Números Finais da Pesquisa Completa

| Rodada | Findings | Fontes | Escopo |
|---|---|---|---|
| 1 (Panorâmica) | F1-F6 | 72 | Módulos, indústrias, concorrentes, compliance, features, integrações |
| 2 (Técnica) | F7-F12 | 84 | Database, events, plugins, SPED/NFe, API, UI config |
| 3 (Infra) | F13-F18 | 90 | Security, performance, DevOps, migration, testing, mobile |
| **Total** | **18 findings files** | **246 fontes** | **Cobertura completa** |

### Dimensões cobertas

- Arquitetura de dados (schema, event sourcing, CQRS, multi-tenancy)
- Comunicação entre módulos (events, sagas, idempotency)
- Sistema de plugins (manifests, lifecycle, auto-install, SemVer)
- Compliance Brasil (SPED, NFe, NFS-e, eSocial, CNPJ, DAS, Simples)
- API design (REST, GraphQL, pagination, versioning, webhooks)
- UI configurável (JSON schema forms, dashboards, PDF, white-label)
- Segurança (encryption, auth, RBAC, PCI, audit trail, LGPD)
- Performance (indexing, caching, pooling, partitioning)
- DevOps (Vercel, migrations, feature flags, backup/DR, observability)
- Migração (OFX, CNAB, QuickBooks, Xero, idempotency)
- Testing (property-based, golden master, time-travel, contract, compliance)
- Mobile/PWA (Serwist, hybrid caching, IndexedDB, WebAuthn, offline sync)

---

## Open Questions Restantes

1. **Transfer pricing**: módulo enterprise para operações cross-border não coberto
2. **ASC 842/IFRS 16**: lease accounting em profundidade
3. **NFS-e**: 5.570 municípios — priorizar top 100
4. **Event sourcing vs traditional**: prototype comparativo necessário
5. **PgBouncer + RLS**: verificar compatibilidade com SET per-transaction
6. **Pricing model**: como precificar módulos (freemium vs tiered vs per-module)
