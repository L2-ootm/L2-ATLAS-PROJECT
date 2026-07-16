# B5: Pricing & Billing Implementation

**Scope**: L2 Cashflow service  
**Date**: 2026-07-10  
**Status**: PLANNING  

---

## 1. Plan Data Model

### 1.1 Entity Relationship

```
Plan ─┬─ PlanTier (Starter/Pro/Enterprise)
      ├─ PlanFeature (feature keys + limits)
      ├─ PlanModule (included modules per tier)
      └─ PlanPricing (currency, intervals, annual discount)

Module ─┬─ ModulePricing (per-module add-on price)
        └─ ModuleCapability (feature flags unlocked)

Subscription ─┬─ SubscriptionTier (current tier FK)
              ├─ SubscriptionModules (purchased add-ons)
              ├─ SubscriptionUsage (metered counters)
              └─ SubscriptionInvoice (billing history)
```

### 1.2 Core Tables

```sql
-- Plans
CREATE TABLE plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(50) UNIQUE NOT NULL,          -- 'starter', 'pro', 'enterprise'
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Pricing per plan
CREATE TABLE plan_pricing (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID REFERENCES plans(id),
    currency VARCHAR(3) DEFAULT 'BRL',
    monthly_price DECIMAL(10,2) NOT NULL,
    annual_price DECIMAL(10,2),                -- NULL = no annual option
    annual_discount_pct DECIMAL(5,2),          -- computed or explicit
    stripe_price_monthly_id VARCHAR(100),      -- Stripe Price ID
    stripe_price_annual_id VARCHAR(100),
    effective_from DATE DEFAULT CURRENT_DATE,
    effective_until DATE,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Feature limits per plan
CREATE TABLE plan_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID REFERENCES plans(id),
    feature_key VARCHAR(100) NOT NULL,         -- 'max_users', 'max_transactions', etc.
    feature_value VARCHAR(255) NOT NULL,        -- '5', '10000', 'unlimited'
    is_unlimited BOOLEAN DEFAULT false,
    UNIQUE(plan_id, feature_key)
);

-- Module inclusions per plan
CREATE TABLE plan_modules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID REFERENCES plans(id),
    module_id UUID REFERENCES modules(id),
    is_included BOOLEAN DEFAULT true,          -- false = available as add-on only
    max_units INT DEFAULT 1,                   -- e.g., max bank accounts
    UNIQUE(plan_id, module_id)
);

-- Module add-on pricing
CREATE TABLE module_pricing (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id UUID REFERENCES modules(id),
    monthly_price DECIMAL(10,2) NOT NULL,
    annual_price DECIMAL(10,2),
    currency VARCHAR(3) DEFAULT 'BRL',
    stripe_price_monthly_id VARCHAR(100),
    stripe_price_annual_id VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Modules
CREATE TABLE modules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    layer VARCHAR(50),                         -- 'core', 'compliance', 'advanced'
    is_core BOOLEAN DEFAULT false,             -- core modules always included
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### 1.3 Plan Definitions

| Feature | Starter (R$79/mo) | Pro (R$199/mo) | Enterprise (R$499/mo) |
|---------|-------------------|----------------|----------------------|
| **Users** | 2 | 10 | Unlimited |
| **Transactions/mo** | 500 | 5,000 | Unlimited |
| **Bank Accounts** | 2 | 10 | Unlimited |
| **Entities** | 1 | 3 | Unlimited |
| **Retention** | 12 months | 36 months | Unlimited |
| **Core Modules** | GL, Bank, Basic Reports | All Core + AP/AR | All Core + AP/AR |
| **Compliance Modules** | — | NFe, SPED | All Compliance |
| **Advanced Modules** | — | — | All Advanced |
| **API Access** | Read-only | Full | Full + Webhooks |
| **Support** | Email | Email + Chat | Email + Chat + Phone |

### 1.4 Feature Key Registry

```python
class FeatureKey(str, Enum):
    MAX_USERS = "max_users"
    MAX_TRANSACTIONS = "max_transactions"
    MAX_BANK_ACCOUNTS = "max_bank_accounts"
    MAX_ENTITIES = "max_entities"
    RETENTION_MONTHS = "retention_months"
    API_ACCESS = "api_access"              # 'read' | 'full' | 'full+webhooks'
    SUPPORT_LEVEL = "support_level"        # 'email' | 'chat' | 'phone'
    NFE_MODULE = "nfe_module"
    SPED_MODULE = "sped_module"
    OPEN_FINANCE_MODULE = "open_finance_module"
    ANALYTICS_MODULE = "analytics_module"
```

---

## 2. Subscription Lifecycle

### 2.1 State Machine

```
                   ┌──────────────────────────────────────┐
                   │                                      │
                   ▼                                      │
    ┌─────────┐   subscribe   ┌──────────┐   payment_ok   │
    │  NONE   │──────────────▶│  TRIAL   │──────────────▶│  ACTIVE
    └─────────┘               └──────────┘               └───────┘
                                              │              │
                                              │ 21 days      │ payment_fail
                                              │ trial_end    │
                                              ▼              ▼
                                       ┌──────────┐   ┌───────────┐
                                       │  PAST_DUE │──▶│  PAUSED   │
                                       └──────────┘   └───────────┘
                                            │              │
                                            │ 30 days      │ user cancels
                                            │ grace        │
                                            ▼              ▼
                                       ┌───────────┐   ┌───────────┐
                                       │ CANCELLED │◀──│ CANCELLING│
                                       └───────────┘   └───────────┘
```

### 2.2 State Definitions

```python
class SubscriptionState(str, Enum):
    NONE = "none"               # No subscription
    TRIAL = "trial"             # 14-day free trial, full Pro features
    ACTIVE = "active"           # Paid, in good standing
    PAST_DUE = "past_due"       # Payment failed, retrying (7-day window)
    PAUSED = "paused"           # Payment repeatedly failed (30-day grace)
    CANCELLING = "cancelling"   # User requested cancel, end-of-period
    CANCELLED = "cancelled"     # Subscription ended, data retained per plan
```

### 2.3 Lifecycle Rules

| Event | From → To | Trigger | Actions |
|-------|-----------|---------|---------|
| **Subscribe** | NONE → TRIAL | User selects plan | Create Stripe subscription, 14-day trial |
| **Trial End** | TRIAL → ACTIVE | 14 days elapsed | First charge attempt |
| **Trial End (no card)** | TRIAL → PAST_DUE | 14 days, no payment method | Grace period reminder emails |
| **Payment Success** | ANY → ACTIVE | Stripe payment_intent.succeeded | Reset dunning counter |
| **Payment Fail** | ACTIVE → PAST_DUE | Stripe payment_intent.payment_failed | Alert user, retry in 3 days |
| **Dunning Retry** | PAST_DUE → PAST_DUE | Auto-retry at +3, +7, +14 days | Email notifications |
| **Dunning Exhausted** | PAST_DUE → PAUSED | 30 days past due | Downgrade to free-tier features |
| **Reactivate** | PAUSED → ACTIVE | User updates payment | Re-enable full features |
| **User Cancel** | ACTIVE → CANCELLING | User clicks cancel | Features until period end |
| **Period End** | CANCELLING → CANCELLED | Billing period expires | Revoke access, retain data |
| **Re-subscribe** | CANCELLED → TRIAL | User selects new plan | New trial period |

### 2.4 Trial Implementation

```python
# services/subscription.py

class SubscriptionService:
    TRIAL_DAYS = 14

    async def start_trial(self, user_id: UUID, plan_id: UUID) -> Subscription:
        subscription = Subscription(
            user_id=user_id,
            plan_id=plan_id,
            state=SubscriptionState.TRIAL,
            trial_start=datetime.utcnow(),
            trial_end=datetime.utcnow() + timedelta(days=self.TRIAL_DAYS),
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=self.TRIAL_DAYS),
        )
        await self.db.add(subscription)

        # Stripe: create subscription with trial
        stripe.Subscription.create(
            customer=user.stripe_customer_id,
            items=[{"price": plan.stripe_price_monthly_id}],
            trial_period_days=self.TRIAL_DAYS,
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"],
        )

        return subscription
```

---

## 3. Billing Engine

### 3.1 Invoice Generation

```sql
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID REFERENCES subscriptions(id),
    stripe_invoice_id VARCHAR(100),
    invoice_number VARCHAR(50) UNIQUE NOT NULL,   -- 'INV-2026-000001'
    status VARCHAR(20) DEFAULT 'draft',           -- draft, open, paid, void, uncollectible
    subtotal DECIMAL(10,2) NOT NULL,
    tax_amount DECIMAL(10,2) DEFAULT 0,
    total DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'BRL',
    due_date DATE,
    paid_at TIMESTAMPTZ,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    billing_reason VARCHAR(50),                   -- 'subscription_create', 'subscription_cycle', 'usage_threshold'
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE invoice_line_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID REFERENCES invoices(id),
    description VARCHAR(255) NOT NULL,
    quantity INT DEFAULT 1,
    unit_price DECIMAL(10,2) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    type VARCHAR(20),                             -- 'subscription', 'add_on', 'usage', 'credit', 'proration'
    plan_id UUID,
    module_id UUID,
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### 3.2 Invoice Generation Flow

```
Billing Cycle Start (1st of month)
    │
    ├─▶ Create draft invoice
    ├─▶ Add base subscription line item
    ├─▶ Add module add-on line items
    ├─▶ Calculate usage overage line items
    ├─▶ Apply coupons/discounts
    ├─▶ Calculate tax (ICMS, ISS, PIS, COFINS)
    ├─▶ Finalize invoice → set status: open
    ├─▶ Send to Stripe for collection
    └─▶ Notify user via email
```

### 3.3 Dunning Configuration

```python
class DunningConfig:
    MAX_RETRY_ATTEMPTS = 4
    RETRY_INTERVALS_DAYS = [0, 3, 7, 14]
    PAUSE_THRESHOLD_DAYS = 30
    GRACE_FEATURES = ["basic_reports", "data_export"]  # Limited features while paused

    EMAIL_SCHEDULE = [
        (0, "payment_failed_first"),      # Immediate
        (3, "payment_failed_reminder"),    # +3 days
        (7, "payment_failed_urgent"),      # +7 days
        (14, "payment_failed_final"),      # +14 days
        (28, "account_paused_warning"),    # +28 days (2 days before pause)
    ]
```

### 3.4 Payment Collection

```python
# services/billing.py

class BillingService:
    async def process_payment(self, invoice: Invoice) -> PaymentResult:
        try:
            # Stripe: attempt payment
            stripe.Invoice.pay(invoice.stripe_invoice_id)

            # Update invoice status
            invoice.status = "paid"
            invoice.paid_at = datetime.utcnow()
            await self.db.update(invoice)

            # Reset subscription state
            if invoice.subscription.state == SubscriptionState.PAST_DUE:
                invoice.subscription.state = SubscriptionState.ACTIVE
                invoice.subscription.dunning_attempts = 0
                await self.db.update(invoice.subscription)

            return PaymentResult(success=True)

        except stripe.error.CardError as e:
            return await self._handle_payment_failure(invoice, e)

    async def _handle_payment_failure(self, invoice: Invoice, error: Exception) -> PaymentResult:
        subscription = invoice.subscription
        subscription.dunning_attempts += 1

        if subscription.dunning_attempts >= DunningConfig.MAX_RETRY_ATTEMPTS:
            subscription.state = SubscriptionState.PAUSED
            await self._downgrade_to_free_tier(subscription)

        elif subscription.state == SubscriptionState.ACTIVE:
            subscription.state = SubscriptionState.PAST_DUE

        await self.db.update(subscription)
        await self._send_dunning_email(subscription, subscription.dunning_attempts)

        return PaymentResult(success=False, error=str(error))
```

---

## 4. Usage Metering

### 4.1 Usage Tracking Table

```sql
CREATE TABLE usage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID REFERENCES subscriptions(id),
    metric_key VARCHAR(50) NOT NULL,              -- 'transactions', 'api_calls', 'users', 'bank_accounts'
    recorded_at TIMESTAMPTZ DEFAULT now(),
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    value DECIMAL(15,4) NOT NULL,                -- count or quantity
    metadata JSONB DEFAULT '{}'
);

-- Materialized view for fast limit checks
CREATE MATERIALIZED VIEW usage_summary AS
SELECT
    subscription_id,
    metric_key,
    period_start,
    SUM(value) as total_usage
FROM usage_records
GROUP BY subscription_id, metric_key, period_start;

CREATE UNIQUE INDEX idx_usage_summary ON usage_summary(subscription_id, metric_key, period_start);
```

### 4.2 Metering Service

```python
# services/metering.py

class MeteringService:
    """Track and enforce plan limits."""

    async def record_usage(self, subscription_id: UUID, metric: str, value: Decimal):
        period_start = self._current_period_start()
        period_end = self._current_period_end()

        record = UsageRecord(
            subscription_id=subscription_id,
            metric_key=metric,
            value=value,
            period_start=period_start,
            period_end=period_end,
        )
        await self.db.add(record)

        # Check limits asynchronously
        await self._check_and_enforce_limits(subscription_id, metric)

    async def get_usage(self, subscription_id: UUID, metric: str) -> UsageSummary:
        period_start = self._current_period_start()
        result = await self.db.execute(
            select(func.sum(UsageRecord.value))
            .where(
                UsageRecord.subscription_id == subscription_id,
                UsageRecord.metric_key == metric,
                UsageRecord.period_start == period_start,
            )
        )
        return UsageSummary(
            metric=metric,
            used=result.scalar() or 0,
            limit=self._get_limit(subscription_id, metric),
            period_start=period_start,
            period_end=self._current_period_end(),
        )

    async def _check_and_enforce_limits(self, subscription_id: UUID, metric: str):
        usage = await self.get_usage(subscription_id, metric)
        if usage.is_exceeded:
            if usage.is_soft_limit:
                # Allow overage, bill extra
                await self._record_overage(subscription_id, metric, usage.overage)
            else:
                # Hard limit: block action
                raise LimitExceededError(metric, usage.used, usage.limit)
```

### 4.3 Usage Metrics

| Metric | Starter | Pro | Enterprise | Hard/Soft |
|--------|---------|-----|------------|-----------|
| `transactions` | 500/mo | 5,000/mo | Unlimited | Soft (overage) |
| `api_calls` | 10,000/mo | 100,000/mo | Unlimited | Soft (overage) |
| `users` | 2 | 10 | Unlimited | Hard (block) |
| `bank_accounts` | 2 | 10 | Unlimited | Hard (block) |
| `entities` | 1 | 3 | Unlimited | Hard (block) |
| `nfe_issued` | — | 100/mo | Unlimited | Soft (overage) |
| `sped_reports` | — | 4/mo | Unlimited | Hard (block) |
| `storage_gb` | 1 | 10 | 100 | Soft (overage) |

### 4.4 Limit Enforcement Middleware

```python
# middleware/limits.py

class PlanLimitMiddleware:
    def __init__(self, metering: MeteringService):
        self.metering = metering

    async def enforce(self, request: Request, metric: str, increment: int = 1):
        subscription = await self._get_subscription(request.user)

        if subscription.plan.is_enterprise:
            return  # Enterprise: no limits

        usage = await self.metering.get_usage(subscription.id, metric)
        limit = usage.limit

        if usage.used + increment > limit:
            if usage.is_soft_limit:
                # Allow but record overage for billing
                await self.metering.record_usage(subscription.id, metric, increment)
                return
            else:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "plan_limit_exceeded",
                        "metric": metric,
                        "used": float(usage.used),
                        "limit": limit,
                        "upgrade_url": f"/settings/billing?upgrade=pro",
                    }
                )

        await self.metering.record_usage(subscription.id, metric, increment)
```

---

## 5. Overage Handling

### 5.1 Overage Pricing

| Metric | Starter Overage | Pro Overage | Enterprise |
|--------|----------------|-------------|------------|
| `transactions` | R$0.20/extra | R$0.15/extra | N/A (unlimited) |
| `api_calls` | R$0.01/1k calls | R$0.008/1k calls | N/A |
| `nfe_issued` | N/A | R$2.50/NFe | R$1.80/NFe |
| `storage_gb` | R$5.00/GB | R$3.50/GB | R$2.00/GB |

### 5.2 Overage Tracking

```sql
CREATE TABLE overage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID REFERENCES subscriptions(id),
    metric_key VARCHAR(50) NOT NULL,
    overage_quantity DECIMAL(15,4) NOT NULL,
    unit_price DECIMAL(10,4) NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    invoice_id UUID REFERENCES invoices(id),     -- linked when invoiced
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### 5.3 Overage Billing Flow

```
1. Usage exceeds plan limit (soft limit)
2. MeteringService records overage in overage_records
3. End of billing period:
   a. BillingService queries all uncharged overages
   b. Groups by metric, calculates total overage amount
   c. Adds overage line items to invoice
   d. Overage records linked to invoice_id
4. Invoice sent to Stripe for collection
```

### 5.4 Overage Notifications

```python
class OverageNotificationService:
    THRESHOLDS = [0.75, 0.90, 1.0, 1.10]  # 75%, 90%, 100%, 110%

    async def check_thresholds(self, subscription_id: UUID, metric: str):
        usage = await self.metering.get_usage(subscription_id, metric)
        usage_pct = usage.used / usage.limit if usage.limit else 0

        for threshold in self.THRESHOLDS:
            if usage_pct >= threshold and not await self._notification_sent(subscription_id, metric, threshold):
                await self._send_threshold_notification(subscription_id, metric, threshold, usage)
                await self._mark_notification_sent(subscription_id, metric, threshold)
```

---

## 6. Module Add-ons

### 6.1 Module Catalog

| Module | Layer | Monthly Price | Annual Price | Description |
|--------|-------|---------------|--------------|-------------|
| **GL + COA** | Core | Included | Included | General ledger, chart of accounts |
| **Bank Reconciliation** | Core | Included | Included | Bank import, matching |
| **Basic Reports** | Core | Included | Included | Standard financial reports |
| **AP/AR** | Core | +R$49 | +R$470 | Accounts payable/receivable |
| **Invoicing** | Core | +R$39 | +R$370 | Invoice generation |
| **NFe** | Compliance | +R$89 | +R$850 | Brazilian electronic invoice |
| **NFS-e** | Compliance | +R$69 | +R$660 | Service electronic invoice |
| **SPED** | Compliance | +R$129 | +R$1,240 | SPED fiscal/contábil |
| **eSocial** | Compliance | +R$149 | +R$1,430 | Employee event reporting |
| **Open Finance** | Compliance | +R$199 | +R$1,910 | Open Finance integration |
| **Multi-Entity** | Advanced | +R$179 | +R$1,720 | Multi-company management |
| **Analytics/BI** | Advanced | +R$149 | +R$1,430 | Advanced analytics |
| **Plugin System** | Advanced | +R$99 | +R$950 | Custom module development |

### 6.2 Purchase Flow

```
User clicks "Add Module"
    │
    ├─▶ Check current plan includes module? → Show "Already included"
    ├─▶ Check if module compatible with plan? → Show upgrade required
    ├─▶ Show pricing (monthly/annual)
    ├─▶ User confirms purchase
    ├─▶ Stripe: create subscription item
    ├─▶ Activate module immediately
    ├─▶ Prorate current period
    └─▶ Send confirmation email
```

### 6.3 Module Activation

```python
# services/module_manager.py

class ModuleManager:
    async def purchase_module(self, user_id: UUID, module_id: UUID, billing: str = "monthly") -> ModulePurchase:
        subscription = await self._get_active_subscription(user_id)
        module = await self._get_module(module_id)
        pricing = await self._get_module_pricing(module_id, billing)

        # Check compatibility
        if not await self._is_compatible(subscription.plan, module):
            raise IncompatibleModuleError(subscription.plan, module)

        # Check if already purchased
        if await self._is_already_purchased(subscription.id, module_id):
            raise ModuleAlreadyPurchasedError(module_id)

        # Create Stripe subscription item
        stripe_item = stripe.SubscriptionItem.create(
            subscription=subscription.stripe_subscription_id,
            price=pricing.stripe_price_id,
            metadata={"module_id": str(module_id)},
        )

        # Record in database
        purchase = SubscriptionModule(
            subscription_id=subscription.id,
            module_id=module_id,
            stripe_item_id=stripe_item.id,
            billing_cycle=billing,
            activated_at=datetime.utcnow(),
        )
        await self.db.add(purchase)

        # Enable module features
        await self._enable_module_features(subscription.id, module)

        # Prorate if mid-period
        if self._is_mid_period(subscription):
            await self._create_proration_invoice(subscription, module, pricing)

        return purchase

    async def deactivate_module(self, user_id: UUID, module_id: UUID):
        subscription = await self._get_active_subscription(user_id)
        purchase = await self._get_module_purchase(subscription.id, module_id)

        # Remove from Stripe
        stripe.SubscriptionItem.delete(purchase.stripe_item_id)

        # Disable module features
        await self._disable_module_features(subscription.id, module_id)

        # Mark as deactivated
        purchase.deactivated_at = datetime.utcnow()
        purchase.status = "inactive"
        await self.db.update(purchase)

        # Prorate credit
        await self._create_proration_credit(subscription, module_id)
```

### 6.4 Module Compatibility Matrix

| Module | Starter | Pro | Enterprise |
|--------|---------|-----|------------|
| GL + COA | ✅ Included | ✅ Included | ✅ Included |
| Bank Reconciliation | ✅ Included | ✅ Included | ✅ Included |
| Basic Reports | ✅ Included | ✅ Included | ✅ Included |
| AP/AR | ✅ Add-on | ✅ Included | ✅ Included |
| Invoicing | ✅ Add-on | ✅ Add-on | ✅ Included |
| NFe | ❌ Upgrade required | ✅ Add-on | ✅ Included |
| NFS-e | ❌ Upgrade required | ✅ Add-on | ✅ Included |
| SPED | ❌ Upgrade required | ✅ Add-on | ✅ Included |
| eSocial | ❌ Upgrade required | ❌ Upgrade required | ✅ Add-on |
| Open Finance | ❌ Upgrade required | ❌ Upgrade required | ✅ Add-on |
| Multi-Entity | ❌ Upgrade required | ❌ Upgrade required | ✅ Add-on |
| Analytics/BI | ❌ Upgrade required | ❌ Upgrade required | ✅ Add-on |
| Plugin System | ❌ Upgrade required | ❌ Upgrade required | ✅ Add-on |

---

## 7. Coupon/Discount Engine

### 7.1 Discount Types

```python
class DiscountType(str, Enum):
    PERCENTAGE = "percentage"         # 10% off
    FIXED_AMOUNT = "fixed_amount"     # R$50 off
    FREE_MONTHS = "free_months"       # 2 months free
    TRIAL_EXTENSION = "trial_extension"  # Extend trial by X days
```

### 7.2 Coupon Table

```sql
CREATE TABLE coupons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    discount_type VARCHAR(20) NOT NULL,
    discount_value DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'BRL',
    max_redemptions INT,                          -- NULL = unlimited
    redeemed_count INT DEFAULT 0,
    applicable_plans UUID[],                      -- NULL = all plans
    applicable_modules UUID[],                    -- NULL = all modules
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE coupon_redemptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    coupon_id UUID REFERENCES coupons(id),
    user_id UUID REFERENCES users(id),
    subscription_id UUID REFERENCES subscriptions(id),
    redeemed_at TIMESTAMPTZ DEFAULT now(),
    discount_amount DECIMAL(10,2) NOT NULL,
    invoice_id UUID REFERENCES invoices(id)
);
```

### 7.3 Volume Discounts

```sql
CREATE TABLE volume_discounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID REFERENCES plans(id),
    min_seats INT NOT NULL,
    max_seats INT,                               -- NULL = unlimited
    discount_pct DECIMAL(5,2) NOT NULL,
    effective_from DATE DEFAULT CURRENT_DATE,
    effective_until DATE,
    is_active BOOLEAN DEFAULT true
);

-- Example: 10+ seats = 15% off, 25+ seats = 25% off
INSERT INTO volume_discounts (plan_id, min_seats, max_seats, discount_pct) VALUES
    ('pro-plan-id', 10, 24, 15.00),
    ('pro-plan-id', 25, NULL, 25.00),
    ('enterprise-plan-id', 10, 49, 10.00),
    ('enterprise-plan-id', 50, NULL, 20.00);
```

### 7.4 Annual Discount

```python
class AnnualDiscountCalculator:
    """Built into plan pricing, not a coupon."""

    ANNUAL_DISCOUNT_PCT = {
        "starter": 20.0,   # R$79/mo → R$63/mo annual = R$756/yr (saves R$192)
        "pro": 20.0,       # R$199/mo → R$159/mo annual = R$1,908/yr (saves R$480)
        "enterprise": 25.0, # R$499/mo → R$374/mo annual = R$4,488/yr (saves R$1,500)
    }

    def calculate_annual_price(self, plan_slug: str, monthly_price: Decimal) -> Decimal:
        discount = self.ANNUAL_DISCOUNT_PCT.get(plan_slug, 0)
        annual_monthly = monthly_price * (1 - discount / 100)
        return (annual_monthly * 12).quantize(Decimal("0.01"))
```

### 7.5 Promo Code Service

```python
class PromoService:
    async def apply_coupon(self, user_id: UUID, code: str) -> CouponResult:
        coupon = await self._get_coupon(code)

        if not coupon or not coupon.is_active:
            raise InvalidCouponError(code)

        if coupon.valid_until < datetime.utcnow():
            raise CouponExpiredError(code)

        if coupon.max_redemptions and coupon.redeemed_count >= coupon.max_redemptions:
            raise CouponLimitReachedError(code)

        # Check if user already redeemed
        if await self._already_redeemed(coupon.id, user_id):
            raise CouponAlreadyRedeemedError(code)

        # Check plan compatibility
        subscription = await self._get_subscription(user_id)
        if coupon.applicable_plans and subscription.plan_id not in coupon.applicable_plans:
            raise CouponIncompatibleError(code, subscription.plan_id)

        # Calculate discount
        discount = self._calculate_discount(coupon, subscription)

        # Record redemption
        redemption = CouponRedemption(
            coupon_id=coupon.id,
            user_id=user_id,
            subscription_id=subscription.id,
            discount_amount=discount,
        )
        await self.db.add(redemption)

        coupon.redeemed_count += 1
        await self.db.update(coupon)

        return CouponResult(discount=discount, coupon=coupon)
```

---

## 8. Tax-Aware Pricing

### 8.1 Brazilian Tax Context

| Tax | Rate | Applies To | Notes |
|-----|------|------------|-------|
| **ICMS** | 18% (SP) | SaaS services | State tax, varies by state |
| **ISS** | 2-5% | Service invoices | Municipal tax |
| **PIS** | 1.65% | Revenue | Federal contribution |
| **COFINS** | 7.6% | Revenue | Federal contribution |
| **IRPJ** | 15% + 10% surcharge | Profit | Corporate income tax |
| **CSLL** | 9% | Profit | Social contribution |

### 8.2 Tax Configuration Table

```sql
CREATE TABLE tax_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tax_type VARCHAR(20) NOT NULL,               -- 'icms', 'iss', 'pis', 'cofins'
    rate DECIMAL(5,2) NOT NULL,
    state_code VARCHAR(2),                       -- UF code for ICMS
    city_code VARCHAR(7),                        -- IBGE code for ISS
    is_inclusive BOOLEAN DEFAULT false,          -- price includes tax?
    effective_from DATE DEFAULT CURRENT_DATE,
    effective_until DATE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Default configuration
INSERT INTO tax_config (tax_type, rate, is_inclusive) VALUES
    ('icms', 18.00, false),
    ('iss', 5.00, false),
    ('pis', 1.65, false),
    ('cofins', 7.60, false);
```

### 8.3 Tax Calculation Service

```python
# services/tax.py

class TaxService:
    async def calculate_tax(self, invoice: Invoice, customer_state: str) -> TaxBreakdown:
        # Determine applicable taxes based on customer location
        taxes = await self._get_applicable_taxes(customer_state)

        subtotal = invoice.subtotal
        tax_amount = Decimal("0.00")
        breakdown = []

        for tax in taxes:
            if tax.is_inclusive:
                # Tax included in price: extract tax amount
                tax_amount = subtotal - (subtotal / (1 + tax.rate / 100))
            else:
                # Tax added on top
                tax_amount = subtotal * (tax.rate / 100)

            breakdown.append(TaxLine(
                tax_type=tax.tax_type,
                rate=tax.rate,
                amount=tax_amount.quantize(Decimal("0.01")),
            ))

            tax_amount += tax_amount

        return TaxBreakdown(
            total_tax=tax_amount.quantize(Decimal("0.01")),
            lines=breakdown,
        )

    async def _get_applicable_taxes(self, state_code: str) -> list[TaxConfig]:
        return await self.db.execute(
            select(TaxConfig).where(
                TaxConfig.is_active == true(),
                TaxConfig.state_code == state_code,
            )
        )
```

### 8.4 Price Display

```python
class PriceDisplayService:
    def format_price(self, amount: Decimal, tax_config: TaxConfig) -> str:
        if tax_config.is_inclusive:
            return f"R$ {amount:.2f} (impostos inclusos)"
        else:
            tax_amount = amount * (tax_config.rate / 100)
            total = amount + tax_amount
            return f"R$ {amount:.2f} + R$ {tax_amount:.2f} impostos = R$ {total:.2f}"
```

---

## 9. Stripe Integration

### 9.1 Stripe Resources

| Resource | Purpose | Key Fields |
|----------|---------|------------|
| `Customer` | Billing identity | `metadata.user_id`, `metadata.org_id` |
| `Subscription` | Active plan | `items`, `status`, `metadata.subscription_id` |
| `Invoice` | Billing document | `lines`, `total`, `status` |
| `PaymentIntent` | Payment attempt | `amount`, `status`, `payment_method` |
| `PaymentMethod` | Card/wallet | `card`, `type` |
| `Coupon` | Discount | `percent_off`, `amount_off`, `duration` |
| `Product` | Plan/module | `metadata.plan_id`, `metadata.module_id` |

### 9.2 Stripe Customer Portal

```python
# services/stripe_portal.py

class StripePortalService:
    async def create_portal_session(self, user_id: UUID) -> PortalSession:
        subscription = await self._get_subscription(user_id)
        customer = await self._get_stripe_customer(user_id)

        session = stripe.billing_portal.Session.create(
            customer=customer.id,
            configuration={
                "business_profile": {
                    "headline": "Gerencie sua assinatura L2 Cashflow",
                    "products": [{
                        "product": subscription.plan.stripe_product_id,
                        "prices": [subscription.plan.stripe_price_monthly_id],
                    }],
                },
                "features": {
                    "subscription_update": {
                        "enabled": True,
                        "default_allowed_updates": ["price", "quantity"],
                        "proration_behavior": "always_invoice",
                    },
                    "subscription_cancel": {
                        "enabled": True,
                        "mode": "at_period_end",
                        "cancellation_reason": {
                            "enabled": True,
                            "options": [
                                "too_expensive",
                                "missing_features",
                                "switched_service",
                                "unused",
                                "other",
                            ],
                        },
                    },
                    "invoice_history": {"enabled": True},
                    "payment_method_update": {"enabled": True},
                    "billing_address_update": {"enabled": True},
                },
            },
            return_url=f"{settings.FRONTEND_URL}/settings/billing",
        )

        return PortalSession(url=session.url, expires_at=session.expires_at)
```

### 9.3 Webhook Handlers

```python
# api/routes/webhooks/stripe.py

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    event = stripe.Webhook.construct_event(
        payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
    )

    match event["type"]:
        case "customer.subscription.created":
            await handle_subscription_created(event["data"]["object"])
        case "customer.subscription.updated":
            await handle_subscription_updated(event["data"]["object"])
        case "customer.subscription.deleted":
            await handle_subscription_deleted(event["data"]["object"])
        case "invoice.paid":
            await handle_invoice_paid(event["data"]["object"])
        case "invoice.payment_failed":
            await handle_invoice_payment_failed(event["data"]["object"])
        case "customer.subscription.trial_will_end":
            await handle_trial_will_end(event["data"]["object"])
        case "payment_method.attached":
            await handle_payment_method_attached(event["data"]["object"])

    return {"status": "ok"}
```

### 9.4 Customer Creation Flow

```python
class CustomerService:
    async def ensure_stripe_customer(self, user: User) -> str:
        if user.stripe_customer_id:
            return user.stripe_customer_id

        customer = stripe.Customer.create(
            email=user.email,
            name=user.full_name,
            metadata={
                "user_id": str(user.id),
                "org_id": str(user.org_id),
            },
            address={
                "country": "BR",
                "state": user.state,
                "city": user.city,
            },
        )

        user.stripe_customer_id = customer.id
        await self.db.update(user)

        return customer.id
```

---

## 10. Upgrade/Downgrade Flow

### 10.1 Proration Rules

| Scenario | Proration | Timing |
|----------|-----------|--------|
| **Upgrade** | Charge difference immediately | Immediate |
| **Downgrade** | Credit difference, apply at period end | At period end |
| **Module Add** | Prorate remaining days | Immediate |
| **Module Remove** | Credit remaining days | At period end |
| **Plan Change (mid-cycle)** | Pro-rata based on days remaining | Immediate |

### 10.2 Upgrade Flow

```python
class PlanChangeService:
    async def upgrade_plan(self, user_id: UUID, new_plan_id: UUID) -> UpgradeResult:
        subscription = await self._get_subscription(user_id)
        new_plan = await self._get_plan(new_plan_id)

        # Validate upgrade
        if new_plan.monthly_price <= subscription.plan.monthly_price:
            raise NotAnUpgradeError(subscription.plan, new_plan)

        # Calculate proration
        days_remaining = (subscription.current_period_end - datetime.utcnow()).days
        days_total = (subscription.current_period_end - subscription.current_period_start).days
        proration_factor = days_remaining / days_total

        old_price = subscription.plan.monthly_price
        new_price = new_plan.monthly_price
        proration_amount = (new_price - old_price) * proration_factor

        # Update Stripe subscription
        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            items=[{
                "id": subscription.stripe_item_id,
                "price": new_plan.stripe_price_monthly_id,
            }],
            proration_behavior="always_invoice",
            metadata={"change_type": "upgrade", "proration_amount": str(proration_amount)},
        )

        # Update database
        subscription.plan_id = new_plan_id
        subscription.upgraded_at = datetime.utcnow()
        await self.db.update(subscription)

        # Enable new features immediately
        await self._enable_plan_features(subscription.id, new_plan)

        # Disable features not in new plan
        await self._disable_removed_features(subscription.id, subscription.plan, new_plan)

        return UpgradeResult(
            proration_amount=proration_amount,
            new_plan=new_plan,
            effective_immediately=True,
        )

    async def downgrade_plan(self, user_id: UUID, new_plan_id: UUID) -> DowngradeResult:
        subscription = await self._get_subscription(user_id)
        new_plan = await self._get_plan(new_plan_id)

        if new_plan.monthly_price >= subscription.plan.monthly_price:
            raise NotADowngradeError(subscription.plan, new_plan)

        # Calculate credit
        days_remaining = (subscription.current_period_end - datetime.utcnow()).days
        days_total = (subscription.current_period_end - subscription.current_period_start).days
        proration_factor = days_remaining / days_total

        old_price = subscription.plan.monthly_price
        new_price = new_plan.monthly_price
        credit_amount = (old_price - new_price) * proration_factor

        # Schedule downgrade for period end
        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            items=[{
                "id": subscription.stripe_item_id,
                "price": new_plan.stripe_price_monthly_id,
            }],
            proration_behavior="none",
            metadata={
                "change_type": "downgrade_pending",
                "effective_date": subscription.current_period_end.isoformat(),
                "credit_amount": str(credit_amount),
            },
        )

        # Schedule feature downgrade
        await self._schedule_feature_downgrade(subscription.id, new_plan, subscription.current_period_end)

        return DowngradeResult(
            credit_amount=credit_amount,
            new_plan=new_plan,
            effective_at=subscription.current_period_end,
            features_active_until=subscription.current_period_end,
        )
```

### 10.3 Data Retention on Cancel

| Plan | Data Retention After Cancel | Export Available |
|------|---------------------------|------------------|
| Starter | 90 days | Yes (CSV) |
| Pro | 180 days | Yes (CSV + API) |
| Enterprise | 1 year | Yes (CSV + API + Archive) |

```python
class CancellationService:
    async def cancel_subscription(self, user_id: UUID, reason: str) -> CancellationResult:
        subscription = await self._get_subscription(user_id)

        # Schedule cancellation at period end
        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=True,
            metadata={"cancellation_reason": reason},
        )

        subscription.state = SubscriptionState.CANCELLING
        await self.db.update(subscription)

        # Set data retention deadline
        retention_days = self._get_retention_days(subscription.plan)
        subscription.data_retention_until = subscription.current_period_end + timedelta(days=retention_days)
        await self.db.update(subscription)

        return CancellationResult(
            effective_at=subscription.current_period_end,
            data_retention_until=subscription.data_retention_until,
            export_available=True,
        )
```

---

## 11. API Endpoints

### 11.1 Plan Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/v1/plans` | List all active plans | Public |
| GET | `/api/v1/plans/{plan_id}` | Get plan details + pricing | Public |
| GET | `/api/v1/modules` | List all available modules | Public |
| GET | `/api/v1/modules/{module_id}` | Get module details + pricing | Public |

### 11.2 Subscription Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/subscriptions` | Create subscription (start trial) | JWT |
| GET | `/api/v1/subscriptions/current` | Get current subscription | JWT |
| PUT | `/api/v1/subscriptions/upgrade` | Upgrade plan | JWT |
| PUT | `/api/v1/subscriptions/downgrade` | Downgrade plan | JWT |
| DELETE | `/api/v1/subscriptions` | Cancel subscription | JWT |
| POST | `/api/v1/subscriptions/reactivate` | Reactivate paused subscription | JWT |

### 11.3 Usage Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/v1/usage` | Get current period usage summary | JWT |
| GET | `/api/v1/usage/{metric}` | Get specific metric usage | JWT |
| GET | `/api/v1/usage/history` | Get usage history (past periods) | JWT |

### 11.4 Billing Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/v1/invoices` | List invoices | JWT |
| GET | `/api/v1/invoices/{invoice_id}` | Get invoice details | JWT |
| POST | `/api/v1/invoices/{invoice_id}/download` | Download invoice PDF | JWT |
| POST | `/api/v1/billing/portal` | Create Stripe portal session | JWT |
| POST | `/api/v1/billing/payment-method` | Update payment method | JWT |

### 11.5 Module Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/modules/purchase` | Purchase module add-on | JWT |
| DELETE | `/api/v1/modules/{module_id}` | Remove module add-on | JWT |
| GET | `/api/v1/modules/active` | List purchased modules | JWT |

### 11.6 Coupon Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/coupons/validate` | Validate promo code | JWT |
| POST | `/api/v1/coupons/apply` | Apply promo code to subscription | JWT |

### 11.7 Request/Response Schemas

```python
# schemas/subscription.py

class CreateSubscriptionRequest(BaseModel):
    plan_id: UUID
    billing_cycle: Literal["monthly", "annual"] = "monthly"
    payment_method_id: str | None = None          # Stripe PM ID
    coupon_code: str | None = None
    trial_days: int | None = None                 # Override default 14

class SubscriptionResponse(BaseModel):
    id: UUID
    state: SubscriptionState
    plan: PlanResponse
    current_period_start: datetime
    current_period_end: datetime
    trial_end: datetime | None
    next_billing_date: datetime
    amount: Decimal
    currency: str
    modules: list[ModuleResponse]
    usage: UsageSummary

class UpgradeRequest(BaseModel):
    new_plan_id: UUID
    billing_cycle: Literal["monthly", "annual"] | None = None
    effective: Literal["immediate", "period_end"] = "immediate"

class UsageSummaryResponse(BaseModel):
    metrics: list[MetricUsage]
    overages: list[OverageRecord]

class MetricUsage(BaseModel):
    metric: str
    used: Decimal
    limit: Decimal | None
    unit: str
    period_start: datetime
    period_end: datetime

class InvoiceResponse(BaseModel):
    id: UUID
    number: str
    status: str
    subtotal: Decimal
    tax_amount: Decimal
    total: Decimal
    currency: str
    due_date: date | None
    paid_at: datetime | None
    line_items: list[LineItemResponse]
    pdf_url: str
```

### 11.8 Error Responses

```python
class PricingError(BaseModel):
    error: str
    code: str
    message: str
    details: dict | None = None
    upgrade_url: str | None = None

# Error codes:
# PLAN_NOT_FOUND
# SUBSCRIPTION_NOT_FOUND
# ALREADY_SUBSCRIBED
# PLAN_LIMIT_EXCEEDED
# MODULE_INCOMPATIBLE
# MODULE_ALREADY_PURCHASED
# COUPON_INVALID
# COUPON_EXPIRED
# COUPON_LIMIT_REACHED
# PAYMENT_FAILED
# UPGRADE_REQUIRED
# CANCELLATION_PENDING
```

---

## 12. Effort Estimate

| Component | Effort (days) | Dependencies | Priority |
|-----------|---------------|--------------|----------|
| **Plan data model + seed data** | 3 | None | P0 |
| **Subscription lifecycle (state machine)** | 5 | Plan model | P0 |
| **Stripe integration (customer, subscription, webhooks)** | 8 | Subscription lifecycle | P0 |
| **Invoice generation** | 5 | Stripe integration | P0 |
| **Usage metering + limit enforcement** | 6 | Plan model, subscription | P0 |
| **Overage tracking + billing** | 4 | Usage metering, invoice | P1 |
| **Module add-on purchase flow** | 5 | Stripe integration, plan model | P1 |
| **Coupon/discount engine** | 4 | Stripe integration | P1 |
| **Tax calculation service** | 4 | Invoice generation | P1 |
| **Upgrade/downgrade + proration** | 6 | Stripe subscription, plan model | P1 |
| **Stripe customer portal config** | 2 | Stripe integration | P1 |
| **API endpoints (all)** | 8 | All services above | P0 |
| **Frontend billing UI** | 10 | API endpoints | P1 |
| **Email notifications (dunning, overage, trial)** | 3 | Subscription lifecycle | P2 |
| **Admin dashboard (revenue, MRR, churn)** | 5 | All billing data | P2 |
| **Testing (unit + integration)** | 8 | All components | P0 |
| **Documentation** | 2 | All components | P2 |
| **TOTAL** | **88 days** | | |

### 12.1 Phase Breakdown

| Phase | Components | Days | Milestone |
|-------|-----------|------|-----------|
| **Phase 1: Core Billing** | Plan model, subscription lifecycle, Stripe integration, API endpoints, tests | 32 | Users can subscribe to plans |
| **Phase 2: Usage & Overage** | Metering, limits, overage tracking, notifications | 10 | Usage-based billing works |
| **Phase 3: Add-ons & Discounts** | Module purchase, coupons, volume discounts | 9 | Module marketplace live |
| **Phase 4: Tax & Proration** | Tax calculation, upgrade/downgrade, proration | 10 | Full billing accuracy |
| **Phase 5: Polish** | Portal config, frontend UI, admin dashboard, docs | 27 | Production ready |

---

## 13. Migration Strategy

### 13.1 Data Migration (Internal → Platform)

```python
class BillingMigrationService:
    """Migrate existing internal users to billing system."""

    async def migrate_internal_users(self):
        # All internal L2 users get Enterprise plan for free
        for user in await self._get_internal_users():
            subscription = Subscription(
                user_id=user.id,
                plan_id=ENTERPRISE_PLAN_ID,
                state=SubscriptionState.ACTIVE,
                is_internal=True,  # Flag for $0 billing
                stripe_subscription_id=None,  # No Stripe for internal
            )
            await self.db.add(subscription)

    async def migrate_external_users(self):
        # External users on legacy system need to select plan
        for user in await self._get_external_users():
            await self._send_migration_email(user, required_by="2026-08-01")
```

### 13.2 Rollback Plan

- Feature flag `billing_enabled` to disable billing entirely
- All billing tables are additive (no existing tables modified)
- Stripe webhooks are idempotent (safe to replay)
- Rollback: disable flag, existing functionality unaffected

---

## Appendix A: Configuration

```yaml
# config/billing.yaml

billing:
  default_trial_days: 14
  currency: BRL
  tax_inclusive: false  # Prices shown without tax

plans:
  starter:
    monthly: 79.00
    annual: 756.00  # 20% discount
    limits:
      users: 2
      transactions: 500
      bank_accounts: 2
      entities: 1
      retention_months: 12
  pro:
    monthly: 199.00
    annual: 1908.00
    limits:
      users: 10
      transactions: 5000
      bank_accounts: 10
      entities: 3
      retention_months: 36
  enterprise:
    monthly: 499.00
    annual: 4488.00  # 25% discount
    limits:
      users: -1  # unlimited
      transactions: -1
      bank_accounts: -1
      entities: -1
      retention_months: -1

dunning:
  max_retries: 4
  retry_days: [0, 3, 7, 14]
  pause_after_days: 30

overage:
  transactions:
    starter: 0.20
    pro: 0.15
    enterprise: 0.00
  api_calls_per_1k:
    starter: 0.01
    pro: 0.008
    enterprise: 0.00
  storage_per_gb:
    starter: 5.00
    pro: 3.50
    enterprise: 2.00

retention_after_cancel:
  starter_days: 90
  pro_days: 180
  enterprise_days: 365
```

---

*End of B5: Pricing & Billing Implementation*
