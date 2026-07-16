# B4: Security Hardening — Production Readiness

**Scope**: L2 Cashflow service  
**Date**: 2026-07-10  
**Status**: PLANNING  

---

## 1. Immediate Fixes

### 1.1 Authentication on All Endpoints

**Current gap**: Zero auth on token webhook endpoint.

| Endpoint | Current Auth | Required Auth |
|----------|-------------|---------------|
| `/webhook/payments` | None | HMAC-SHA256 signature verification |
| `/api/v1/transactions` | Session only | JWT + RBAC |
| `/api/v1/accounts` | Session only | JWT + RBAC |
| `/health` | None | None (keep open) |

**Implementation**:
```python
# middleware/auth.py
class HMACWebhookVerifier:
    def verify(self, payload: bytes, signature: str, secret: str) -> bool:
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
```

**JWT structure**:
```json
{
  "sub": "user_id",
  "org": "org_id",
  "roles": ["viewer", "editor"],
  "exp": 1720000000,
  "iss": "cashflow.l2atlas.com"
}
```

### 1.2 Input Validation

**Current gap**: `data: any` allows arbitrary payloads.

**Fix**: Replace all `data: any` with strict Pydantic models:

```python
# BEFORE
class TransactionAction(BaseModel):
    data: Any

# AFTER
class TransactionAction(BaseModel):
    amount: Decimal = Field(ge=0, le=99999999.99)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    description: str = Field(max_length=500)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode='after')
    def validate_amount_precision(self):
        if self.amount.as_tuple().exponent < -2:
            raise ValueError("Amount max 2 decimal places")
        return self
```

**Validation layers**:
- Pydantic v2 models (request body)
- Path parameter regex (UUID format, numeric IDs)
- Query parameter type coercion + bounds
- SQL parameterization (already done via SQLAlchemy)

### 1.3 Remove `data: any` Audit

| File | Location | Fix |
|------|----------|-----|
| `models/actions.py` | TransactionAction.data | Replace with typed fields |
| `models/actions.py` | ReconciliationAction.data | Replace with typed fields |
| `models/actions.py` | AdjustmentAction.data | Replace with typed fields |
| `api/routes/webhooks.py` | Raw payload handling | Add schema validation |

---

## 2. Encryption at Rest

### 2.1 PII Fields

**Fields requiring encryption**:
- `cpf` (CPF/CNPJ)
- `bank_account_number`
- `bank_agency`
- `pix_key`

**Approach**: AES-256-GCM with envelope encryption.

```python
# crypto/encryption.py
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

class FieldEncryption:
    def __init__(self, master_key: bytes):
        self.master_key = master_key

    def encrypt_field(self, plaintext: str) -> bytes:
        dek = os.urandom(32)  # Data encryption key
        nonce = os.urandom(12)
        aesgcm = AESGCM(dek)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)

        # Encrypt DEK with master key (envelope encryption)
        encrypted_dek = self._wrap_key(dek)

        # Format: version(1) + nonce(12) + encrypted_dek(32) + ciphertext(variable)
        return b'\x01' + nonce + encrypted_dek + ciphertext

    def decrypt_field(self, blob: bytes) -> str:
        version = blob[0]
        nonce = blob[1:13]
        encrypted_dek = blob[13:45]
        ciphertext = blob[45:]

        dek = self._unwrap_key(encrypted_dek)
        aesgcm = AESGCM(dek)
        return aesgcm.decrypt(nonce, ciphertext, None).decode()
```

### 2.2 Database Column Encryption

- **Transparent encryption**: PostgreSQL pgcrypto for column-level encryption
- **Searchable encryption**: Hashed index for exact-match lookups on CPF
- **Key storage**: AWS KMS / HashiCorp Vault (see §4)

### 2.3 Backup Encryption

- All database backups encrypted with separate key
- Backup retention: 30 days daily, 12 months monthly
- Restore procedure tested quarterly

---

## 3. Encryption in Transit

### 3.1 TLS 1.3 Enforcement

```nginx
# nginx.conf
ssl_protocols TLSv1.3;
ssl_ciphers TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256;
ssl_prefer_server_ciphers on;
ssl_session_timeout 1d;
ssl_session_tickets off;
```

### 3.2 mTLS for Service-to-Service

**Certificate hierarchy**:
```
Root CA (offline)
├── Intermediate CA (Vault PKI)
│   ├── cashflow-service
│   ├── cashflow-worker
│   └── cashflow-cron
└── Client CA
    ├── api-gateway
    └── internal-services
```

**Implementation**: Service mesh (Istio/Linkerd) or manual mTLS with cert-manager.

### 3.3 Certificate Rotation

- Automated rotation every 90 days
- Zero-downtime rotation via rolling restart
- OCSP stapling enabled

---

## 4. Secrets Management

### 4.1 Migration Path: Env Vars → Vault

**Phase 1: Inventory** (Week 1)
- Catalog all env vars containing secrets
- Classify: database, API keys, tokens, certificates
- Map to Vault paths

**Phase 2: Vault Setup** (Week 2-3)
```
cashflow/
├── database/
│   ├── postgres/cred/postgres-rw
│   ├── postgres/cred/postgres-ro
│   └── redis/cred/default
├── api-keys/
│   ├── external/payment-gateway
│   └── external/open-finance
└── certificates/
    └── tls/cashflow-service
```

**Phase 3: Dual Read** (Week 4)
- App reads from Vault first, falls back to env var
- Logging: track which source was used

**Phase 4: Vault Only** (Week 5)
- Remove env vars from deployment configs
- Vault becomes source of truth

### 4.2 Key Rotation Schedule

| Secret | Rotation | Automation |
|--------|----------|------------|
| Database credentials | 30 days | Vault dynamic secrets |
| API keys | 90 days | Manual + alerts |
| TLS certificates | 90 days | cert-manager |
| Encryption master key | 365 days | Manual (HSM) |
| JWT signing key | 180 days | Manual |

---

## 5. PCI DSS

### 5.1 Scope Reduction via Tokenization

**Current state**: Cashflow handles transaction metadata, not card numbers directly.

**Tokenization flow**:
```
Client → Payment Gateway (tokenize) → Cashflow (store token, not PAN)
                                        ↓
                              Token → Gateway (detokenize for refunds)
```

**PCI scope**: Cardholder data never touches Cashflow servers → SAQ A-EP or SAQ A.

### 5.2 SAQ Assessment

| Requirement | Status | Action |
|-------------|--------|--------|
| Req 1: Firewall | To verify | Confirm cloud firewall rules |
| Req 2: Defaults | To verify | Disable default accounts |
| Req 3: Protect stored data | Partial | Encrypt PII fields |
| Req 4: Encrypt transmission | Planned | TLS 1.3 (§3) |
| Req 5: AV software | N/A | Cloud-native |
| Req 6: Secure systems | Planned | Hardening checklist |
| Req 7: Access restriction | Planned | RBAC implementation |
| Req 8: Authenticate access | Planned | MFA + JWT (§1) |
| Req 9: Physical access | N/A | Cloud provider |
| Req 10: Log & monitor | Planned | Audit trail (§6) |
| Req 11: Test security | Planned | Pen testing (§8) |
| Req 12: Security policy | Planned | Document policies |

### 5.3 Data Flow Diagram

```
[User Browser] 
    → [Cloudflare WAF]
    → [API Gateway] (TLS termination, rate limiting)
    → [Cashflow Service] (no PAN storage)
    → [PostgreSQL] (encrypted PII, no card data)
    → [Payment Gateway] (PCI DSS L1 certified)
```

---

## 6. Audit Trail

### 6.1 Immutable Audit Log

**Design**: Append-only log with hash-chaining (blockchain-style).

```python
# audit/log.py
import hashlib
import json
from datetime import datetime, timezone

class AuditEntry:
    def __init__(self, action: str, actor: str, resource: str, 
                 details: dict, previous_hash: str):
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.action = action
        self.actor = actor
        self.resource = resource
        self.details = details
        self.previous_hash = previous_hash
        self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        content = json.dumps({
            "timestamp": self.timestamp,
            "action": self.action,
            "actor": self.actor,
            "resource": self.resource,
            "details": self.details,
            "previous_hash": self.previous_hash
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "actor": self.actor,
            "resource": self.resource,
            "details": self.details,
            "previous_hash": self.previous_hash,
            "hash": self.hash
        }
```

### 6.2 Audit Events

| Event | Trigger | Retention |
|-------|---------|-----------|
| `auth.login` | Successful login | 2 years |
| `auth.login.failed` | Failed login | 1 year |
| `auth.logout` | Logout | 2 years |
| `transaction.create` | Transaction created | 7 years |
| `transaction.update` | Transaction modified | 7 years |
| `transaction.delete` | Transaction deleted | 7 years |
| `account.access` | Account data accessed | 2 years |
| `settings.change` | Configuration modified | 2 years |
| `export.generate` | Data export initiated | 2 years |
| `user.permission_change` | RBAC change | 2 years |

### 6.3 Tamper Evidence

- Daily hash-chain verification job
- Alert if chain broken
- External backup of hash roots (S3 with Object Lock)

---

## 7. LGPD/GDPR

### 7.1 Consent Management

**Consent model**:
```python
class Consent(BaseModel):
    user_id: UUID
    purpose: Literal["marketing", "analytics", "third_party_sharing"]
    granted: bool
    timestamp: datetime
    version: str  # Policy version at time of consent
    ip_address: str
    user_agent: str
```

**Consent flows**:
- **Collection**: Explicit opt-in at registration
- **Storage**: Encrypted, immutable audit log
- **Withdrawal**: One-click, immediate effect
- **Verification**: API endpoint for consent status check

### 7.2 Data Minimization

**Principle**: Collect only what's needed, retain only as long as required.

| Data Type | Necessity | Retention | Action |
|-----------|-----------|-----------|--------|
| CPF/CNPJ | Tax compliance | 5 years | Encrypt at rest |
| Bank account | Transaction processing | 3 years | Encrypt at rest |
| Transaction metadata | Financial tracking | 7 years | Standard storage |
| User preferences | UX | Until deletion | Non-PII |
| Audit logs | Compliance | 2 years | Append-only |

### 7.3 Right to Deletion

**Deletion flow**:
1. User requests deletion via `/api/v1/gdpr/deletion`
2. System identifies all data locations
3. Soft-delete with 30-day grace period
4. Verify no legal holds
5. Hard-delete: cryptographic erasure (delete encryption keys)
6. Confirm deletion to user
7. Audit log entry (retained for compliance)

**Cryptographic erasure**:
```python
async def crypto_erase_user(user_id: UUID):
    """Delete all encryption keys for a user's data."""
    await vault.delete(f"cashflow/users/{user_id}/keys")
    await db.execute(
        "DELETE FROM user_data_keys WHERE user_id = $1", user_id
    )
    await audit.log("gdpr.deletion.crypto_erase", user_id)
```

---

## 8. Penetration Testing

### 8.1 OWASP ZAP Automation

**Weekly scan schedule**:
```yaml
# .github/workflows/security-scan.yml
name: Security Scan
on:
  schedule:
    - cron: '0 2 * * 1'  # Monday 2 AM
  workflow_dispatch:

jobs:
  zap-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: zaproxy/action-full-scan@v0.10.0
        with:
          target: https://cashflow-staging.l2atlas.com
          rules_file_name: 'rules.tsv'
          cmd_options: '-a'
```

### 8.2 Burp Suite Testing

**Manual testing checklist**:

- [ ] **Authentication**
  - [ ] JWT signature bypass
  - [ ] Token expiration bypass
  - [ ] Role escalation
  - [ ] Session fixation
  - [ ] Password policy enforcement

- [ ] **Authorization**
  - [ ] IDOR on transaction endpoints
  - [ ] Horizontal privilege escalation
  - [ ] Vertical privilege escalation
  - [ ] API key scope bypass

- [ ] **Input Validation**
  - [ ] SQL injection (all parameters)
  - [ ] XSS (reflected, stored, DOM)
  - [ ] Command injection
  - [ ] Path traversal
  - [ ] File upload vulnerabilities

- [ ] **Business Logic**
  - [ ] Negative amount injection
  - [ ] Race conditions on transfers
  - [ ] Double-spend attempts
  - [ ] Amount precision manipulation

- [ ] **Cryptographic**
  - [ ] Key exposure in logs
  - [ ] Weak cipher suites
  - [ ] Certificate validation bypass
  - [ ] Side-channel leaks

### 8.3 Remediation SLA

| Severity | Fix Deadline | Verification |
|----------|--------------|--------------|
| Critical | 24 hours | Immediate retest |
| High | 7 days | Automated scan |
| Medium | 30 days | Next sprint review |
| Low | 90 days | Quarterly review |

---

## 9. Security Monitoring

### 9.1 Intrusion Detection

**Detection rules** (Wazuh/Suricata):
```yaml
# rules/cashflow-custom.yml
- alert: Brute Force Login
  condition: >
    rate(src_ip, 5min) > 10 AND
    event_type = 'auth.login.failed'
  severity: HIGH
  action: block_ip(src_ip, 1h)

- alert: Unusual Data Export
  condition: >
    event_type = 'export.generate' AND
    export_size > 1000000
  severity: MEDIUM
  action: notify_admin

- alert: Privilege Escalation Attempt
  condition: >
    event_type = 'user.permission_change' AND
    new_role = 'admin' AND
    actor_role != 'superadmin'
  severity: CRITICAL
  action: block_and_notify
```

### 9.2 Anomaly Alerts

**Metrics to monitor**:
- Login failure rate (baseline: <5/hour per user)
- Transaction velocity (baseline: <100/hour per account)
- API response time (baseline: p99 < 500ms)
- Error rate (baseline: <1%)
- Data export volume (baseline: <10MB/day per user)

**Alert channels**:
- Critical: PagerDuty + Slack #security-critical
- High: Slack #security-alerts
- Medium: Email to security team
- Low: Weekly digest

### 9.3 Log Aggregation

**Architecture**:
```
Cashflow Service → Fluentd → Elasticsearch → Kibana
                    ↓
              S3 (long-term, encrypted)
```

**Log retention**:
- Hot (Elasticsearch): 30 days
- Warm (S3 Standard): 90 days
- Cold (S3 Glacier): 1 year

---

## 10. Incident Response

### 10.1 Incident Severity Levels

| Level | Description | Response Time | Example |
|-------|-------------|---------------|---------|
| P0 | Active data breach | 15 minutes | Unauthorized data access |
| P1 | System compromise | 1 hour | Server breach |
| P2 | Security vulnerability | 4 hours | Critical CVE |
| P3 | Suspicious activity | 24 hours | Failed brute force |
| P4 | Policy violation | 1 week | Shared credentials |

### 10.2 Communication Templates

**Internal notification (P0)**:
```
SECURITY INCIDENT - P0
Time: {timestamp}
Detection: {source}
Impact: {description}
Status: Investigating
Incident Lead: {name}
War Room: {link}
Next Update: {time}
```

**External notification (if breach)**:
```
Subject: Security Notice - L2 Cashflow

Dear {user_name},

We are writing to inform you of a security incident that may have 
affected your personal data.

What happened: {brief_description}
When: {date_range}
What data: {affected_data_types}
What we're doing: {remediation_steps}
What you can do: {user_actions}

We take this matter seriously and have {actions_taken}.

For questions: security@l2atlas.com

L2 Cashflow Security Team
```

### 10.3 Post-Mortem Process

**Template**:
```markdown
# Incident Post-Mortem

## Summary
- **Date**: 
- **Duration**: 
- **Severity**: 
- **Impact**: 

## Timeline
- HH:MM: Event detected
- HH:MM: Investigation started
- HH:MM: Containment actions
- HH:MM: Resolution

## Root Cause
[Detailed technical explanation]

## What Went Well
- [list]

## What Could Be Improved
- [list]

## Action Items
| Action | Owner | Due | Status |
|--------|-------|-----|--------|
| [item] | [name] | [date] | [status] |

## Lessons Learned
[key_takeaways]
```

---

## 11. SOC 2 Preparation

### 11.1 Trust Service Criteria

| Criteria | Cashflow Controls | Evidence |
|----------|-------------------|----------|
| **CC6.1** Logical access controls | JWT + RBAC | Access logs, RBAC config |
| **CC6.2** Credentials management | Vault + rotation | Vault audit logs |
| **CC6.3** Access removal | Automated offboarding | Deprovisioning logs |
| **CC6.6** Encryption | AES-256-GCM + TLS 1.3 | Crypto config, certs |
| **CC7.1** Vulnerability management | ZAP + Burp scans | Scan reports |
| **CC7.2** Monitoring | Wazuh + alerts | Alert history |
| **CC8.1** Change management | Git + CI/CD | PR reviews, deploy logs |
| **CC9.1** Risk assessment | Annual review | Risk register |

### 11.2 Evidence Collection

**Automated evidence**:
```python
# evidence/collector.py
class EvidenceCollector:
    def collect_access_logs(self, period: str) -> Path:
        """Export access logs for auditor review."""
        return self.export(f"access-logs-{period}.json")

    def collect_crypto_config(self) -> Path:
        """Document encryption configuration."""
        return self.export("crypto-config.json")

    def collect_scan_reports(self, period: str) -> Path:
        """Aggregate security scan results."""
        return self.export(f"scan-reports-{period}.zip")

    def collect_incident_reports(self, period: str) -> Path:
        """Export incident response records."""
        return self.export(f"incidents-{period}.json")
```

### 11.3 Compliance Checklist

- [ ] Security policies documented
- [ ] Access control matrix defined
- [ ] Encryption standards documented
- [ ] Incident response plan tested
- [ ] Vendor assessments completed
- [ ] Employee security training
- [ ] Background checks for privileged access
- [ ] Regular access reviews (quarterly)
- [ ] Vulnerability scanning schedule
- [ ] Penetration testing (annual)
- [ ] Business continuity plan
- [ ] Disaster recovery tested

---

## 12. Effort Estimate

| Security Domain | Effort (person-weeks) | Priority | Dependencies |
|-----------------|----------------------|----------|--------------|
| **1. Immediate Fixes** | 2 | P0 | None |
| Auth on endpoints | 1 | | JWT library |
| Input validation | 1 | | Pydantic models |
| **2. Encryption at Rest** | 3 | P0 | Vault setup |
| PII field encryption | 2 | | AES-GCM library |
| Backup encryption | 1 | | Cloud storage |
| **3. Encryption in Transit** | 2 | P0 | None |
| TLS 1.3 | 0.5 | | Nginx config |
| mTLS | 1.5 | | cert-manager |
| **4. Secrets Management** | 4 | P1 | Vault infrastructure |
| Vault setup | 2 | | Infrastructure |
| Migration | 2 | | Testing |
| **5. PCI DSS** | 2 | P1 | §1, §2, §3 |
| Tokenization | 1 | | Payment gateway |
| SAQ documentation | 1 | | All controls |
| **6. Audit Trail** | 3 | P1 | None |
| Hash-chain implementation | 2 | | Database schema |
| Verification jobs | 1 | | Cron setup |
| **7. LGPD/GDPR** | 3 | P1 | None |
| Consent management | 1.5 | | Frontend |
| Deletion flow | 1.5 | | Crypto erasure |
| **8. Penetration Testing** | 2 | P2 | §1-§3 |
| ZAP automation | 0.5 | | CI/CD |
| Burp manual testing | 1.5 | | Staging env |
| **9. Security Monitoring** | 3 | P2 | None |
| Wazuh setup | 1 | | Infrastructure |
| Alerting rules | 1 | | Log aggregation |
| Dashboard | 1 | | Kibana |
| **10. Incident Response** | 1 | P2 | None |
| Plan documentation | 0.5 | | Templates |
| Tabletop exercise | 0.5 | | Team |
| **11. SOC 2** | 4 | P3 | §1-§10 |
| Policy documentation | 2 | | Legal review |
| Evidence collection | 1 | | Automation |
| Auditor preparation | 1 | | External |
| **TOTAL** | **29** | | |

---

## 13. Implementation Timeline

### Phase 1: Critical (Weeks 1-4)
- §1: Immediate fixes (auth, validation)
- §2: Encryption at rest (PII fields)
- §3: TLS 1.3 enforcement

### Phase 2: Core (Weeks 5-12)
- §4: Vault migration
- §6: Audit trail
- §7: LGPD/GDPR

### Phase 3: Hardening (Weeks 13-20)
- §5: PCI DSS compliance
- §8: Penetration testing
- §9: Security monitoring

### Phase 4: Compliance (Weeks 21-28)
- §10: Incident response
- §11: SOC 2 preparation

---

## 14. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Auth coverage | 100% endpoints | Automated scan |
| PII encryption | 100% fields | Code review |
| TLS 1.3 | 100% traffic | SSL Labs A+ |
| Vulnerability count | 0 critical/high | Weekly scans |
| Incident response time | <15 min P0 | Post-mortem |
| Audit log integrity | 100% chain valid | Daily verification |
| SOC 2 readiness | Pass audit | External auditor |

---

**Next steps**:
1. Review with security team
2. Get budget approval for Vault infrastructure
3. Begin Phase 1 implementation
4. Schedule first pen test
