# B5 — PLG & Growth Engine

> Batch 5 · Growth & Synthesis · 2026-07-10
> Core thesis: every sent invoice is an acquisition channel.

---

## 1. Activation Tracking

### 1.1 Activation Events

| Event | Weight | Time Window | Scoring |
|---|---|---|---|
| First invoice created | 30 | 24h | Binary (0/30) |
| Bank account connected | 25 | 72h | Binary (0/25) |
| Team member invited | 20 | 7 days | Binary (0/20) |
| Second invoice sent | 15 | 14 days | Binary (0/15) |
| First report generated | 10 | 30 days | Binary (0/10) |

### 1.2 PQL Scoring Model

```
pql_score = Σ(event_weight × completion_flag × recency_decay)

recency_decay = max(0, 1 - (days_since_signup / window_days))
```

| Score Range | Classification | Action |
|---|---|---|
| 80–100 | Hot PQL | Sales outreach within 24h |
| 50–79 | Warm PQL | Automated nurture + optional sales touch |
| 20–49 | Engaged | Product-led nurture (email, in-app) |
| 0–19 | At-risk | Re-engagement campaign |

### 1.3 Data Collection

```sql
CREATE TABLE activation_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  user_id UUID NOT NULL REFERENCES users(id),
  event_type VARCHAR(50) NOT NULL, -- 'first_invoice', 'bank_connected', etc.
  event_data JSONB DEFAULT '{}',
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(tenant_id, user_id, event_type)
);

CREATE INDEX idx_activation_tenant_user ON activation_events(tenant_id, user_id);
CREATE INDEX idx_activation_type_time ON activation_events(event_type, occurred_at);
```

### 1.4 PQL Identification Pipeline

```
Event emitted → activation_events table
  → pg_notify('activation_channel', event)
  → Worker recalculates pql_score for tenant
  → If score crosses threshold → create PQL record
  → PQL record triggers: sales assignment (enterprise) or nurture sequence (SMB)
```

---

## 2. Viral Loops

### 2.1 Invoice-as-Viral-Vector

The strongest PLG lever. Every invoice sent is a touchpoint.

```
User sends invoice → Recipient sees invoice
  → "Powered by L2 Cashflow" branding on footer
  → CTA: "Manage your invoicing with L2 Cashflow — Free"
  → Recipient signs up → Sends their own invoices → Loop repeats
```

**Branding controls:**

| Plan | Branding | Customization |
|---|---|---|
| Free | L2 Cashflow footer + logo | None |
| Starter | L2 Cashflow footer (smaller) | Logo, colors |
| Pro | No L2 branding | Full white-label |
| Enterprise | No L2 branding + custom domain | Full control |

### 2.2 Shareable Dashboards

```typescript
interface ShareableDashboard {
  dashboard_id: string;
  tenant_id: string;
  share_token: string;         // cryptographically random, 32 bytes
  permissions: 'view_only' | 'interactive';
  expires_at: string | null;   // null = never
  created_by: string;
}

// Public route: /dashboards/shared/:token
// Renders read-only dashboard with L2 Cashflow CTA
// CTA links to signup with ref=dashboard_share_{dashboard_id}
```

### 2.3 Viral Coefficient Targets

| Metric | Target | How |
|---|---|---|
| Invites per active user | 2.5 | Invoice recipients + team invites |
| Invite conversion rate | 20% | CTA on invoices + dashboards |
| Viral coefficient (K) | 0.5 | 2.5 × 0.20 |
| K > 1.0 timeline | Month 18+ | Requires product-market fit + referral program |

---

## 3. Self-Serve Upgrade

### 3.1 Upgrade Triggers

| Trigger | Context | Prompt |
|---|---|---|
| Invoice limit reached | Free tier: 20 invoices/month | "Unlock unlimited invoices — Upgrade to Starter" |
| Bank connection attempt | Free tier: 0 bank connections | "Connect your bank with Pro — Start free trial" |
| Team invite attempt | Free tier: 1 user | "Add your team — Starter includes 3 users" |
| Report generation | Free tier: basic reports only | "Unlock advanced analytics — Upgrade to Pro" |
| API access attempt | Free tier: no API | "Access the API — Pro includes full API access" |
| Export attempt | Free tier: PDF only | "Export to Excel/CSV — Starter includes all formats" |

### 3.2 Trial-to-Paid Conversion

```
Free user hits limit
  → Show upgrade modal with value proposition
  → "Start 14-day Pro trial — no credit card required"
  → Trial activated
  → Day 3: "You've used X features this week"
  → Day 7: "Your trial is halfway — here's what you'd lose"
  → Day 12: "2 days left — upgrade now to keep your data"
  → Day 14: Trial ends → graceful degradation (read-only access)
```

### 3.3 Usage-Based Pricing Tiers

| Tier | Price | Limits |
|---|---|---|
| Free | R$0/mo | 20 invoices, 1 user, basic reports |
| Starter | R$99/mo | 200 invoices, 3 users, bank connection |
| Pro | R$299/mo | Unlimited invoices, 10 users, API, advanced reports |
| Enterprise | Custom | Unlimited everything, SSO, audit log, SLA |

### 3.4 Upgrade Prompt Design

- **Never block mid-action.** Show prompt after action completes (or fails due to limit).
- **Show ROI.** "You sent 18 invoices this month. At R$99/mo, that's R$5.50 per invoice."
- **Anchor to competitor.** "Competitors charge R$199/mo for this. We're R$99."
- **Social proof.** "2,400+ businesses upgraded this month."
- **Urgency.** "Your data is safe — but you can't create new invoices until you upgrade."

---

## 4. PLG + Sales Hybrid

### 4.1 Segment Routing

```
Signup → Segment classifier
  ├─ SMB (1-10 employees, <R$1M ARR)
  │   └─ Pure PLG: self-serve, in-app upgrade, automated nurture
  ├─ Mid-market (11-100 employees, R$1M-10M ARR)
  │   └─ PLG-assisted: PQL triggers optional sales touch
  └─ Enterprise (100+ employees, >R$10M ARR)
      └─ PQL → sales outreach, demo, custom proposal
```

### 4.2 PQL → Sales Handoff

```typescript
interface PQLRecord {
  tenant_id: string;
  pql_score: number;
  classification: 'hot' | 'warm' | 'engaged';
  signals: ActivationSignal[];
  company_data: {
    name: string;
    size_estimate: string;
    industry: string;
    invoice_volume: number;
  };
  assigned_sales_rep: string | null;
  status: 'new' | 'contacted' | 'qualified' | 'disqualified' | 'converted';
}
```

### 4.3 Sales Outreach Triggers

| Trigger | SLA | Action |
|---|---|---|
| Hot PQL (score 80+) | 24h | SDR calls + emails |
| Warm PQL (score 50-79) | 72h | Automated email + optional call |
| Enterprise signup | 4h | Immediate SDR assignment |
| 3+ team members invited | 24h | "Team adoption" outreach |
| API usage spike | 48h | "Need help scaling?" outreach |

---

## 5. Churn Prevention

### 5.1 Usage-Based Churn Signals

| Signal | Weight | Threshold |
|---|---|---|
| Invoice frequency drop | 30 | >50% decrease from 30-day avg |
| Login frequency drop | 25 | <2 logins in 14 days |
| Feature usage decline | 20 | Using <30% of activated features |
| Support ticket spike | 15 | 3+ unresolved tickets in 30 days |
| Payment failure | 10 | 2+ failed payment attempts |

### 5.2 Churn Score Calculation

```
churn_score = Σ(signal_weight × severity × recency)

severity = actual_value / expected_value  (lower = higher risk)
recency = 1 - (days_since_signal / 30)
```

| Score Range | Risk Level | Action |
|---|---|---|
| 0.0–0.3 | Low | No action |
| 0.3–0.6 | Medium | Automated re-engagement email |
| 0.6–0.8 | High | Customer success call |
| 0.8–1.0 | Critical | Retention offer (discount, free month) |

### 5.3 Proactive Outreach

| Day | Action | Channel |
|---|---|---|
| Day 0 | Churn signal detected | Internal alert |
| Day 1 | Automated "We noticed you haven't been active" email | Email |
| Day 3 | Check if email opened | Email analytics |
| Day 5 | Customer success call (if high-value) | Phone |
| Day 7 | Retention offer (if no response) | Email + in-app |
| Day 14 | Final attempt + survey | Email |
| Day 30 | Downgrade to free tier | Automated |

### 5.4 Re-engagement Campaigns

| Campaign | Trigger | Content |
|---|---|---|
| "Come back" | 14 days inactive | New features, case studies |
| "We miss you" | 30 days inactive | Discount offer, personal note |
| "Last chance" | 60 days inactive | Account deletion warning |
| "Win-back" | 90 days inactive | Fresh start offer, re-onboarding |

---

## 6. Referral Program

### 6.1 Referral Tracking

```sql
CREATE TABLE referrals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  referrer_tenant_id UUID NOT NULL REFERENCES tenants(id),
  referred_tenant_id UUID REFERENCES tenants(id),
  referral_code VARCHAR(20) NOT NULL UNIQUE,
  channel VARCHAR(50) NOT NULL, -- 'invoice_footer', 'dashboard_share', 'direct_link'
  status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending/qualified/converted/expired
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  qualified_at TIMESTAMPTZ,
  converted_at TIMESTAMPTZ
);

CREATE TABLE referral_rewards (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  referral_id UUID NOT NULL REFERENCES referrals(id),
  reward_type VARCHAR(30) NOT NULL, -- 'credit', 'extended_trial', 'feature_unlock'
  reward_value NUMERIC(10,2) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending/issued/expired
  issued_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ
);
```

### 6.2 Referral Program Structure

| Milestone | Referrer Reward | Referred Reward |
|---|---|---|
| Referred signs up | R$20 credit | 14-day Pro trial |
| Referred sends first invoice | R$50 credit | — |
| Referred upgrades to paid | 10% of referred's first 3 months | 1 month free |
| 5 successful referrals | "Ambassador" badge + priority support | — |
| 10+ referrals | Revenue share (5% of referred ARR) | — |

### 6.3 Attribution Model

```
Referral tracked via:
  1. Referral code in URL: ?ref=ABC123
  2. Invoice footer CTA: "Powered by L2 Cashflow (invited by {referrer})"
  3. Dashboard share: "Shared by {referrer} via L2 Cashflow"
  4. Direct link: shareable signup link with embedded ref

Attribution window: 90 days from first click
Last-touch attribution: most recent referral source wins
```

---

## 7. Content Strategy

### 7.1 SEO for Financial Terms

**Primary keywords (BR market):**

| Keyword | Monthly Volume | Difficulty | Priority |
|---|---|---|---|
| "software contabilidade" | 12,000 | High | Pillar |
| "emissor de nota fiscal" | 8,100 | High | Pillar |
| "fluxo de caixa" | 6,600 | Medium | Pillar |
| "gestão financeira" | 5,400 | Medium | Supporting |
| "fatura online" | 3,600 | Low | Quick win |
| "controle financeiro empresa" | 2,900 | Low | Quick win |

### 7.2 Comparison Pages

| Page | Competitors | Target Keyword |
|---|---|---|
| "L2 Cashflow vs TOTVS" | TOTVS | "TOTVS alternativa" |
| "L2 Cashflow vs Dominio" | Dominio Sistemas | "Dominio alternativa" |
| "L2 Cashflow vs Omie" | Omie | "Omie alternativa" |
| "L2 Cashflow vs Conta Azul" | Conta Azul | "Conta Azul alternativa" |
| "L2 Cashflow vs QuickBooks BR" | QuickBooks | "QuickBooks Brasil alternativa" |

### 7.3 Educational Content

| Content Type | Topics | Frequency |
|---|---|---|
| Blog posts | "How to manage cash flow for [industry]" | 2x/week |
| Guides | "Complete guide to NF-e compliance" | 1x/month |
| Templates | Free COA templates, invoice templates | 4x/month |
| Webinars | "Tax planning for MEI" | 2x/month |
| Case studies | Customer success stories | 1x/month |

### 7.4 Content-to-PLG Pipeline

```
Blog post (SEO traffic)
  → Content upgrade (free template/checklist)
  → Email capture (lead magnet)
  → Onboarding sequence (5 emails over 14 days)
  → Product activation (first invoice)
  → Conversion (paid plan)
```

---

## 8. Community

### 8.1 Developer Community

| Channel | Purpose | Launch |
|---|---|---|
| GitHub | Open-source SDK, plugin examples | Month 1 |
| Discord | Real-time developer support | Month 1 |
| Docs site | API reference, guides, tutorials | Month 1 |
| Plugin marketplace | Community plugins | Month 3 |

### 8.2 User Groups

| Group | Audience | Frequency |
|---|---|---|
| "Cashflow Masters" | Power users, accountants | Monthly meetup |
| "Startup Finance" | Founders, CFOs | Bi-weekly |
| "Industry Roundtables" | Restaurant, retail, services | Quarterly |

### 8.3 Open-Source Contributions

| Component | License | Rationale |
|---|---|---|
| Invoice template engine | MIT | Drive adoption, attract contributors |
| COA template library | CC0 | Community-driven, zero friction |
| Tax calculation rules | Apache 2.0 | Transparency builds trust |
| SDK/client libraries | MIT | Ecosystem growth |

---

## 9. Metrics Dashboard

### 9.1 North Star Metrics

| Metric | Target | Formula |
|---|---|---|
| Activation rate | >40% | Users completing magic action / signups |
| Time-to-value | <5 min | Signup → first invoice |
| Conversion rate | >5% | Paid / Free signups |
| Net Dollar Retention (NRR) | >120% | (MRR_start + expansion - contraction - churn) / MRR_start |
| Viral coefficient (K) | >0.5 | Invites/user × conversion rate |

### 9.2 Growth Metrics

| Metric | Frequency | Alert Threshold |
|---|---|---|
| Daily signups | Daily | <7-day average × 0.7 |
| Activation rate | Weekly | <35% |
| Trial-to-paid | Weekly | <4% |
| Churn rate | Monthly | >5% |
| Referral rate | Monthly | <10% of signups |
| LTV/CAC ratio | Monthly | <3:1 |

### 9.3 PLG Health Score

```
plg_health = (
  activation_rate × 0.25 +
  conversion_rate × 0.25 +
  nrr × 0.20 +
  viral_coefficient × 0.15 +
  (1 - churn_rate) × 0.15
) × 100

Score > 70: Healthy
Score 40-70: Needs attention
Score < 40: Critical
```

### 9.4 Dashboard Components

```
/ analytics / growth
  ├── Overview panel (signups, activation, conversion trend)
  ├── Cohort analysis (retention by signup month)
  ├── Funnel visualization (visitor → signup → activate → convert)
  ├── Viral loop metrics (K-factor, referrals, invoice-as-vector)
  ├── PQL pipeline (hot/warm/engaged counts, conversion rates)
  ├── Churn risk board (at-risk accounts, scores, actions taken)
  └── Revenue metrics (MRR, ARR, expansion, contraction)
```

---

## 10. API Endpoints

### 10.1 Activation Tracking

```typescript
// POST /api/v1/activation/events
// Track activation event for current user
{
  "event_type": "first_invoice" | "bank_connected" | "team_invited" | "second_invoice" | "report_generated",
  "event_data": Record<string, any>
}

// Response:
{
  "event_id": "uuid",
  "pql_score": 55,
  "activation_progress": 3,  // number of activation events completed
  "next_suggested_action": "Connect your bank account"
}
```

### 10.2 PQL Score

```typescript
// GET /api/v1/pql/:tenant_id
// Get PQL score and classification for a tenant
// Requires: admin or sales role

// Response:
{
  "tenant_id": "uuid",
  "pql_score": 75,
  "classification": "warm",
  "signals": [
    { "type": "first_invoice", "score": 30, "completed": true, "at": "2026-07-10T14:00:00Z" },
    { "type": "bank_connected", "score": 25, "completed": true, "at": "2026-07-10T15:30:00Z" },
    { "type": "team_invited", "score": 20, "completed": false, "at": null },
    { "type": "second_invoice", "score": 0, "completed": false, "at": null },
    { "type": "report_generated", "score": 0, "completed": false, "at": null }
  ],
  "company": { "name": "Acme Ltda", "size": "11-50", "industry": "services" },
  "assigned_rep": null
}
```

### 10.3 Referral System

```typescript
// POST /api/v1/referrals/generate
// Generate a referral link for current tenant
// Response:
{
  "referral_code": "ACME2026",
  "referral_link": "https://cashflow.l2.com.br/signup?ref=ACME2026",
  "qr_code_url": "https://cashflow.l2.com.br/api/v1/referrals/ACME2026/qr"
}

// GET /api/v1/referrals
// List all referrals for current tenant
// Response:
{
  "referrals": [
    {
      "id": "uuid",
      "referred_email": "partner@example.com",
      "status": "converted",
      "created_at": "2026-06-15T10:00:00Z",
      "converted_at": "2026-06-20T14:30:00Z",
      "rewards": [
        { "type": "credit", "amount": 70, "status": "issued" }
      ]
    }
  ],
  "total_referrals": 5,
  "total_rewards": 350
}

// GET /api/v1/referrals/stats
// Aggregated referral statistics
// Response:
{
  "total_referrals": 5,
  "pending": 1,
  "qualified": 2,
  "converted": 2,
  "total_rewards_issued": 350,
  "conversion_rate": 0.40,
  "viral_coefficient": 0.52
}
```

### 10.4 Churn Prevention

```typescript
// GET /api/v1/churn/risk
// List tenants at risk of churn
// Requires: admin or success role

// Response:
{
  "at_risk": [
    {
      "tenant_id": "uuid",
      "tenant_name": "Acme Ltda",
      "churn_score": 0.75,
      "risk_level": "high",
      "signals": [
        { "type": "login_frequency_drop", "severity": 0.8 },
        { "type": "invoice_frequency_drop", "severity": 0.6 }
      ],
      "last_active": "2026-07-01T09:00:00Z",
      "mrr": 299,
      "suggested_action": "Customer success call"
    }
  ],
  "summary": {
    "total_at_risk": 12,
    "high_risk_mrr": 3588,
    "medium_risk_mrr": 1196
  }
}
```

---

## 11. Effort Estimate

| Component | Effort | Dependencies | Priority |
|---|---|---|---|
| **Activation tracking** | 2 weeks | Event system, user table | P0 |
| **PQL scoring model** | 1 week | Activation events | P0 |
| **Invoice-as-viral-vector** | 1.5 weeks | Invoice system, branding | P0 |
| **Self-serve upgrade prompts** | 2 weeks | Billing system, limits | P0 |
| **Referral program** | 2 weeks | Activation tracking | P1 |
| **Shareable dashboards** | 1.5 weeks | Analytics/BI | P1 |
| **Churn prevention** | 2 weeks | PQL scoring, usage events | P1 |
| **PLG + sales hybrid** | 1 week | PQL, CRM integration | P1 |
| **Content strategy (SEO)** | 4 weeks ongoing | Marketing, CMS | P2 |
| **Community (Discord/GitHub)** | 1 week setup + ongoing | — | P2 |
| **Metrics dashboard** | 2 weeks | Analytics/BI, data pipeline | P1 |
| **API endpoints** | 2 weeks | All above | P0 |

### Summary

| Category | Total Effort |
|---|---|
| Core PLG (activation + upgrade + viral) | 6.5 weeks |
| Growth loops (referral + churn + sales) | 5 weeks |
| Content + community | 5 weeks |
| API + metrics | 4 weeks |
| **Total** | **~20 weeks (5 months)** |

### Phase Ordering

| Phase | Weeks | Components |
|---|---|---|
| 1 — Foundation | 1–3 | Activation tracking, PQL scoring, API endpoints |
| 2 — Viral | 4–6 | Invoice branding, shareable dashboards, self-serve upgrade |
| 3 — Growth | 7–10 | Referral program, churn prevention, sales hybrid |
| 4 — Scale | 11–15 | Content strategy, community, metrics dashboard |
| 5 — Optimize | 16–20 | A/B testing, cohort analysis, PQL refinement |

---

## Appendix: Key Benchmarks

| Metric | SaaS Average | Fintech Average | L2 Target |
|---|---|---|---|
| Trial-to-paid | 2–5% | 5–10% | >5% |
| Activation rate | 25–40% | 30–45% | >40% |
| NRR | 100–110% | 110–130% | >120% |
| Viral coefficient | 0.1–0.3 | 0.2–0.5 | >0.5 |
| Payback period | 12–18 months | 6–12 months | <12 months |
| LTV/CAC | 3:1 | 4:1 | >4:1 |
| Monthly churn | 3–7% | 2–5% | <3% |
