# B3: Payment Gateway Integration Layer — Brazil

## Overview

Design a unified payment abstraction layer supporting 4 Brazilian payment providers (Asaas, PagSeguro, Mercado Pago, Stripe Brasil) with common interfaces for Pix, boleto, card payments, and subscription billing. The layer must be provider-agnostic, webhook-driven, and idempotent.

---

## 1. Provider Adapter Pattern

### Architecture

```
┌─────────────────────────────────────────────────┐
│              PaymentService (Orchestrator)       │
│  - createPayment() → delegates to adapter        │
│  - routes by provider enum                       │
│  - maintains audit log                           │
└───────────┬─────────────────────────────────────┘
            │
    ┌───────▼────────┐
    │ PaymentAdapter │  ← interface (abstract)
    │ (common)       │
    └───────┬────────┘
            │
  ┌─────────┼──────────┬──────────────┬──────────────┐
  │         │          │              │              │
Asaas   PagSeguro   MercadoPago   StripeBR      (future)
```

### Core Interface (`PaymentAdapter`)

```typescript
interface PaymentAdapter {
  readonly provider: ProviderEnum;

  // Payment lifecycle
  createPayment(req: CreatePaymentRequest): Promise<PaymentResult>;
  capturePayment(paymentId: string, amount?: number): Promise<PaymentResult>;
  cancelPayment(paymentId: string): Promise<PaymentResult>;
  refundPayment(paymentId: string, amount?: number): Promise<RefundResult>;

  // Query
  getPayment(paymentId: string): Promise<PaymentStatus>;
  listPayments(filter: PaymentFilter): Promise<PaginatedPayments>;

  // Subscription
  createSubscription(req: CreateSubscriptionRequest): Promise<SubscriptionResult>;
  cancelSubscription(subscriptionId: string): Promise<void>;
  updateSubscriptionPaymentMethod(subscriptionId: string, method: PaymentMethodUpdate): Promise<void>;

  // Webhooks
  parseWebhook(payload: unknown, headers: Record<string, string>): WebhookEvent;
  verifyWebhookSignature(payload: string, headers: Record<string, string>): boolean;

  // Fees
  calculateFee(amount: number, method: PaymentMethod): FeeBreakdown;
}
```

### Factory Pattern

```typescript
class PaymentAdapterFactory {
  private adapters: Map<ProviderEnum, () => PaymentAdapter>;

  register(provider: ProviderEnum, factory: () => PaymentAdapter): void;

  getAdapter(provider: ProviderEnum): PaymentAdapter {
    // Lazy instantiation, singleton per provider
  }

  getAvailableProviders(): ProviderEnum[] {
    // Only returns providers with valid API keys configured
  }
}
```

### Data Models

```typescript
type ProviderEnum = 'asaas' | 'pagseguro' | 'mercadopago' | 'stripe';
type PaymentMethod = 'pix' | 'boleto' | 'credit_card' | 'debit_card';
type PaymentStatusEnum = 'pending' | 'processing' | 'approved' | 'declined' | 'refunded' | 'cancelled' | 'expired' | 'chargeback';

interface CreatePaymentRequest {
  amount: number;           // cents
  currency: 'BRL';
  method: PaymentMethod;
  description: string;
  externalId: string;       // idempotency key
  customer: CustomerData;
  metadata?: Record<string, string>;
  dueDate?: string;         // ISO date, for boleto
  installments?: number;    // card only
}

interface PaymentResult {
  providerId: string;
  providerPaymentId: string;
  status: PaymentStatusEnum;
  amount: number;
  fee: number;
  netAmount: number;
  paymentUrl?: string;      // checkout redirect
  pixQrCode?: string;       // base64 or URL
  pixCopyPaste?: string;    // PIX copy-paste code
  boletoUrl?: string;       // boleto PDF URL
  boletoBarCode?: string;   // boleto barcode
  expiresAt?: string;
}

interface FeeBreakdown {
  gatewayFee: number;       // cents
  antifraudFee: number;     // cents
  iofFee: number;           // cents (international cards)
  netAmount: number;        // cents
}
```

### Directory Structure

```
lib/payments/
├── index.ts                    # exports
├── types.ts                    # shared types
├── PaymentService.ts           # orchestrator
├── PaymentAdapterFactory.ts    # factory
├── adapters/
│   ├── asaas/
│   │   ├── AsaasAdapter.ts
│   │   ├── asaas.types.ts
│   │   ├── asaas.client.ts     # HTTP client wrapper
│   │   └── asaas.webhooks.ts
│   ├── pagseguro/
│   │   ├── PagSeguroAdapter.ts
│   │   ├── pagseguro.types.ts
│   │   ├── pagseguro.client.ts
│   │   └── pagseguro.webhooks.ts
│   ├── mercadopago/
│   │   ├── MercadoPagoAdapter.ts
│   │   ├── mercadopago.types.ts
│   │   ├── mercadopago.client.ts
│   │   └── mercadopago.webhooks.ts
│   └── stripe/
│       ├── StripeBRAdapter.ts
│       ├── stripeBR.types.ts
│       ├── stripeBR.client.ts
│       └── stripeBR.webhooks.ts
├── webhooks/
│   ├── WebhookRouter.ts        # routes to correct adapter
│   ├── WebhookStore.ts         # idempotency tracking
│   └── signature-verifier.ts   # HMAC verification utilities
├── subscriptions/
│   ├── SubscriptionManager.ts
│   └── dunning.ts              # retry/failed payment logic
└── fees/
    └── FeeCalculator.ts        # per-provider fee tables
```

---

## 2. Asaas Integration

### API Reference

- Base URL: `https://api.asaas.com/v3`
- Auth: API key via `access_token` header
- Docs: https://docs.asaas.com/

### Supported Payment Methods

| Method | Endpoint | Status |
|--------|----------|--------|
| Pix | `/payments` with `billingType: PIX` | Production |
| Boleto | `/payments` with `billingType: BOLETO` | Production |
| Credit Card | `/payments` with `billingType: CREDIT_CARD` | Production |
| Debit Card | `/payments` with `billingType: DEBIT_CARD` | Production |

### Create Payment (Asaas)

```typescript
// POST /payments
{
  "customer": "cus_xxx",          // Asaas customer ID
  "billingType": "PIX",           // PIX | BOLETO | CREDIT_CARD | DEBIT_CARD
  "value": 100.00,
  "dueDate": "2026-07-15",
  "description": "Invoice #1234",
  "externalReference": "ext_1234", // our idempotency key
  "pixQrCodeId": "optional",
  "creditCard": {                 // card only
    "creditCardNumber": "...",
    "creditCardHolderName": "...",
    "creditCardDueMonth": 12,
    "creditCardDueYear": 2027,
    "creditCardCcv": "123"
  }
}
```

### Asaas Webhooks

Event types to handle:

| Event | Trigger | Action |
|-------|---------|--------|
| `PAYMENT_RECEIVED` | Payment confirmed | Mark approved, reconcile |
| `PAYMENT_OVERDUE` | Payment past due | Trigger dunning |
| `PAYMENT_DELETED` | Payment cancelled | Mark cancelled |
| `PAYMENT_REFUNDED` | Refund processed | Mark refunded |
| `PAYMENT_CHARGEBACK_REQUESTED` | Chargeback initiated | Freeze, alert |
| `PAYMENT_CHARGEBACK_DISPUTE` | Chargeback dispute | Legal workflow |
| `SUBSCRIPTION_CREATED` | Subscription created | Link to account |
| `SUBSCRIPTION_UPDATED` | Subscription changed | Sync plan |
| `SUBSCRIPTION_DELETED` | Subscription cancelled | Mark inactive |

### Asaas Subscription Model

Asaas supports native recurring billing:
- `POST /subscriptions` with `billingType`, `cycle` (MONTHLY/QUARTERLY/YEARLY)
- Automatic retry on failure
- `POST /subscriptions/{id}/payment` to manually trigger
- `DELETE /subscriptions/{id}` to cancel

### Asaas-Specific Notes

- Asaas manages PIX key registration internally
- Boleto generation is automatic; PDF URL returned in response
- Customer must be created first (`POST /customers`) before payment
- Idempotency via `externalReference` field

---

## 3. PagSeguro Integration

### API Reference

- Base URL: `https://api.pagseguro.com`
- Auth: Bearer token
- Docs: https://dev.pagseguro.uol.com.br/

### Supported Payment Methods

| Method | Flow | Notes |
|--------|------|-------|
| Pix | Direct | QR code + copy-paste |
| Boleto | Direct | 3-day expiry default |
| Credit Card | Checkout | Hosted or transparent |
| Debit Card | Checkout | Limited issuers |

### Create Payment (PagSeguro)

```typescript
// POST /orders
{
  "reference_id": "ext_1234",
  "customer": {
    "name": "Davi Silva",
    "email": "davi@l2systems.com.br",
    "tax_id": "123.456.789-00",
    "phones": [{ "area_code": "11", "number": "99999-9999" }]
  },
  "items": [{
    "id": "item_001",
    "name": "Service Payment",
    "quantity": 1,
    "unit_amount": 10000  // cents
  }],
  "payment_methods": [{
    "type": "PIX",
    "pix": { "expiration_date": "2026-07-15T23:59:00Z" }
  }],
  "payment_method": "PIX"
}
```

### PagSeguro Webhooks

Events via `POST /orders/{id}/notifications`:

| Event | Action |
|-------|--------|
| `ORDER.PAYMENT.AUTHORIZED` | Payment authorized, capture |
| `ORDER.PAYMENT.CAPTURED` | Payment captured |
| `ORDER.PAYMENT.DECLINED` | Payment rejected |
| `ORDER.PAYMENT.REFUNDED` | Refund processed |
| `ORDER.PAYMENT.CHARGEBACK` | Chargeback received |
| `ORDER.CANCELLED` | Order cancelled |

### PagSeguro Checkout

Two modes:
1. **Transparent Checkout** (recommended): iframe embedded in our page, card data never touches our server (PCI compliance)
2. **Hosted Checkout**: redirect to PagSeguro page, simpler but less control

### PagSeguro-Specific Notes

- PagSeguro uses a two-step flow: create → authorize → capture
- Pix QR codes expire after configurable period (default 30 min)
- Boleto has 3-day expiry; auto-cancels after
- Customer must be created as CPF/CNPJ holder

---

## 4. Mercado Pago Integration

### API Reference

- Base URL: `https://api.mercadopago.com/v1`
- Auth: Bearer token (OAuth or App token)
- Docs: https://www.mercadopago.com.br/developers

### Supported Payment Methods

| Method | Notes |
|--------|-------|
| Pix | Instant, QR + copy-paste |
| Boleto | 3-day expiry |
| Credit Card | Installments up to 12x |
| Debit Card | Limited |

### Create Payment (Mercado Pago)

```typescript
// POST /payments
{
  "transaction_amount": 100.00,
  "description": "Service Payment",
  "external_reference": "ext_1234",
  "payment_method_id": "pix",
  "payer": {
    "email": "davi@l2systems.com.br",
    "first_name": "Davi",
    "last_name": "Silva",
    "identification": {
      "type": "CPF",
      "number": "123.456.789-00"
    }
  },
  "date_of_expiration": "2026-07-15T20:00:00.000-03:00",
  "metadata": { "key": "value" }
}
```

### Mercado Pago Webhooks

| Topic | Event | Action |
|-------|-------|--------|
| `payment` | `payment.created` | New payment registered |
| `payment` | `payment.updated` | Status changed |
| `merchant_order` | Order updated | Full order status |

### Mercado Pago Checkout

- **Checkout Pro**: hosted page with all payment methods
- **Checkout API**: transparent integration (recommended)
- **Checkout Bricks**: pre-built UI components

### Mercado Pago Subscriptions

- `POST /preapproval` for recurring billing
- `cycle` = MONTHLY, YEARLY
- Auto-retry on failure (configurable)
- `PUT /preapproval/{id}` to update plan

### Mercado Pago Split Payments

Marketplace model:
- `split` parameter in payment creation
- `marketplace_fee` = platform commission
- `collector_id` = seller's MP user ID
- Fee deducted before settlement

### Mercado Pago-Specific Notes

- OAuth required for multi-seller marketplaces
- `external_reference` is the idempotency key
- Payment status: `pending`, `approved`, `authorized`, `in_process`, `rejected`, `cancelled`, `refunded`, `charged_back`
- PIX payments: QR code returned in `point_of_interaction.transaction_data`

---

## 5. Stripe Brasil Integration

### API Reference

- Base URL: `https://api.stripe.com/v1`
- Auth: Secret key (sk_live_xxx / sk_test_xxx)
- Docs: https://stripe.com/docs/api
- Brasil-specific: https://stripe.com/docs/payments/payment-methods/brazil

### Supported Payment Methods

| Method | Notes |
|--------|-------|
| Pix | Via PaymentIntents |
| Boleto | Via PaymentIntents with `boleto` type |
| Credit Card | Native Stripe flow |
| Debit Card | Limited support |

### Create Payment (Stripe Brasil)

```typescript
// Stripe: PaymentIntent (unified)
const intent = await stripe.paymentIntents.create({
  amount: 10000,           // cents
  currency: 'brl',
  payment_method_types: ['pix', 'boleto', 'card'],
  metadata: { external_id: 'ext_1234' },
  receipt_email: 'davi@l2systems.com.br',
  description: 'Service Payment',
  payment_method_options: {
    boleto: { expires_after_days: 3 },
    pix: { expires_after_seconds: 1800 }
  }
});

// For card: create PaymentMethod → attach → confirm
const pm = await stripe.paymentMethods.create({
  type: 'card',
  card: {
    number: '4242...',
    exp_month: 12,
    exp_year: 2027,
    cvc: '123'
  },
  billing_details: { name: 'Davi Silva' }
});
```

### Stripe Brasil Webhooks

| Event | Action |
|-------|--------|
| `payment_intent.succeeded` | Payment completed |
| `payment_intent.payment_failed` | Payment failed |
| `charge.refunded` | Refund processed |
| `charge.dispute.created` | Chargeback initiated |
| `customer.subscription.created` | Subscription active |
| `customer.subscription.updated` | Plan changed |
| `customer.subscription.deleted` | Subscription cancelled |
| `invoice.payment_succeeded` | Invoice paid |
| `invoice.payment_failed` | Invoice failed (dunning) |

### Stripe Checkout Sessions

```typescript
const session = await stripe.checkout.sessions.create({
  payment_method_types: ['card', 'boleto', 'pix'],
  line_items: [{
    price_data: {
      currency: 'brl',
      product_data: { name: 'Service Payment' },
      unit_amount: 10000,
    },
    quantity: 1,
  }],
  mode: 'payment',
  success_url: 'https://app.l2systems.com.br/payment/success',
  cancel_url: 'https://app.l2systems.com.br/payment/cancel',
  metadata: { external_id: 'ext_1234' }
});
```

### Stripe Connect (Marketplace)

For multi-tenant platform with split payments:

```typescript
// Create connected account for seller
const account = await stripe.accounts.create({
  type: 'standard',  // or 'express' for simpler flow
  country: 'BR',
  email: 'seller@example.com',
  capabilities: {
    card_payments: { requested: true },
    transfers: { requested: true },
  },
});

// Create payment with destination charge
const paymentIntent = await stripe.paymentIntents.create({
  amount: 10000,
  currency: 'brl',
  application_fee_amount: 1500,  // platform fee
  transfer_data: { destination: account.id },
  payment_method_types: ['card', 'boleto', 'pix'],
});
```

### Stripe Subscriptions

```typescript
const subscription = await stripe.subscriptions.create({
  customer: 'cus_xxx',
  items: [{ price: 'price_xxx' }],
  payment_behavior: 'default_incomplete',
  payment_settings: {
    save_default_payment_method: 'on_subscription',
  },
  expand: ['latest_invoice.payment_intent'],
});
```

### Stripe Brasil-Specific Notes

- PIX: PaymentIntent returns `next_action.pix.qr_code` and `next_action.pix.data_url`
- Boleto: PaymentIntent returns `next_action.boleto.hosted_voucher_url`
- Card: full 3D Secure support for SCA compliance
- `application_fee_amount` for marketplace split (in cents)
- Subscriptions: use Stripe's native dunning (configurable retry logic)

---

## 6. Common Interface Methods

### `createPayment(req: CreatePaymentRequest) → PaymentResult`

1. Validate request (amount > 0, required fields)
2. Generate idempotency key from `req.externalId`
3. Look up provider adapter via factory
4. Call adapter's `createPayment()`
5. Store result in `payments` table
6. Emit `payment.created` event
7. Return result with payment URLs/codes

### `capturePayment(paymentId: string, amount?: number) → PaymentResult`

1. Look up payment in DB
2. Call adapter's `capturePayment()` (or `confirm()` for Stripe)
3. Update payment status
4. Emit `payment.captured` event
5. Return updated result

### `refundPayment(paymentId: string, amount?: number) → RefundResult`

1. Look up original payment
2. Validate refund eligibility (not already refunded, within window)
3. Call adapter's `refundPayment()`
4. Create refund record
5. Emit `payment.refunded` event
6. Return refund details

### `listTransactions(filter: PaymentFilter) → PaginatedPayments`

1. Query local DB first (fast path)
2. If `syncWithProvider: true`, also fetch from provider API
3. Merge and deduplicate
4. Apply filters (status, method, date range, customer)
5. Return paginated results

### `handleWebhook(payload, headers) → void`

1. Extract provider signature from headers
2. Find matching adapter
3. Verify signature
4. Parse event into `WebhookEvent`
5. Check idempotency (has this event been processed?)
6. Execute business logic based on event type
7. Mark event as processed
8. Emit corresponding internal events

---

## 7. Webhook Handling

### Signature Verification

Each provider uses different signature mechanisms:

| Provider | Header | Algorithm |
|----------|--------|-----------|
| Asaas | `asaas-access-token` | API key match |
| PagSeguro | `X-Hub-Signature-256` | HMAC-SHA256 |
| Mercado Pago | `x-signature` | HMAC-SHA256 with timestamp |
| Stripe | `Stripe-Signature` | HMAC-SHA256 with `t=...&v1=...` |

### Idempotent Processing

```typescript
// WebhookStore: tracks processed events
interface WebhookEventRecord {
  id: string;                // provider event ID
  provider: ProviderEnum;
  type: string;
  receivedAt: Date;
  processedAt?: Date;
  status: 'pending' | 'processed' | 'failed';
  payload: string;           // raw JSON
  error?: string;
}

// Idempotency check before processing
async function processEvent(event: WebhookEvent): Promise<void> {
  const existing = await db.webhookEvents.findUnique({
    where: { provider_event_id: event.providerEventId }
  });
  if (existing?.status === 'processed') return; // skip

  // Upsert + mark processing
  await db.webhookEvents.upsert({
    where: { provider_event_id: event.providerEventId },
    create: { ...event, status: 'processing' },
    update: { status: 'processing' }
  });

  try {
    await executeBusinessLogic(event);
    await db.webhookEvents.update({
      where: { provider_event_id: event.providerEventId },
      data: { status: 'processed', processedAt: new Date() }
    });
  } catch (err) {
    await db.webhookEvents.update({
      where: { provider_event_id: event.providerEventId },
      data: { status: 'failed', error: err.message }
    });
    throw err; // let provider retry
  }
}
```

### Retry Handling

- Providers retry webhooks automatically (typically 3-5 times over 24-72h)
- Return HTTP 200 on success, non-200 on failure
- Never block webhook endpoint — accept, queue, process async
- Use a job queue (BullMQ/Inngest) for async processing

### Webhook Endpoint

```
POST /api/webhooks/payments/:provider

Route → WebhookRouter → Adapter.parseWebhook() → Adapter.verifyWebhookSignature() → WebhookStore.processEvent()
```

---

## 8. Payment Status Synchronization

### Primary: Webhook-Driven

```
Provider → Webhook → parse → verify → store → business logic → update DB → emit event
```

### Fallback: Polling

When webhooks are unreliable or for status reconciliation:

```typescript
class PaymentPoller {
  // Poll every 5 minutes for pending payments
  async pollPendingPayments(): Promise<void> {
    const pending = await db.payments.findMany({
      where: {
        status: 'pending',
        provider: { in: ['asaas', 'pagseguro', 'mercadopago', 'stripe'] },
        lastPolledAt: { lt: subMinutes(new Date(), 5) }
      }
    });

    for (const payment of pending) {
      const adapter = factory.getAdapter(payment.provider);
      const status = await adapter.getPayment(payment.providerPaymentId);
      if (status !== payment.status) {
        await updatePaymentStatus(payment.id, status);
      }
      await db.payments.update({
        where: { id: payment.id },
        data: { lastPolledAt: new Date() }
      });
    }
  }
}
```

### Reconciliation Job

- Run daily at 02:00 BRT
- Compare local DB state vs provider API state
- Flag discrepancies for manual review
- Auto-resolve minor discrepancies (e.g., settled vs approved)

---

## 9. Recurring Billing

### Subscription Management

```typescript
interface Subscription {
  id: string;
  externalId: string;
  customerId: string;
  provider: ProviderEnum;
  providerSubscriptionId: string;
  planId: string;
  status: 'active' | 'past_due' | 'cancelled' | 'paused';
  amount: number;
  currency: 'BRL';
  billingCycle: 'monthly' | 'quarterly' | 'yearly';
  currentPeriodStart: Date;
  currentPeriodEnd: Date;
  paymentMethod: PaymentMethod;
  retryCount: number;
  maxRetries: number;
}
```

### Dunning (Failed Payment Recovery)

```
Day 0: Payment fails
Day 1: Email notification + retry 1
Day 3: Email reminder + retry 2
Day 7: SMS + email + retry 3
Day 14: Final notice, auto-cancel if unpaid
```

Implementation:
- Track `retryCount` on subscription
- Use provider's native retry logic when available (Asaas, Stripe)
- Custom retry for providers without native dunning (PagSeguro, Mercado Pago)
- Exponential backoff: 1h → 24h → 72h → 7d

### Payment Method Updater

- Stripe: Automatic Card Account Updater (ACU)
- Asaas: Manual update via `PUT /subscriptions/{id}/paymentMethod`
- Others: Manual update required
- Trigger: `customer.subscription.updated` event with `payment_settings.payment_method_updated`

---

## 10. Fee Calculation

### Per-Provider Fee Structures (BRL)

| Provider | Method | Fee | Additional |
|----------|--------|-----|-----------|
| **Asaas** | Pix | 0.99% | Min R$1.49 |
| | Boleto | R$3.99 | flat |
| | Credit Card | 2.99% | + R$0.40 per tx |
| | Debit Card | 1.99% | + R$0.40 per tx |
| **PagSeguro** | Pix | 0.99% | Min R$0.99 |
| | Boleto | R$3.49 | flat |
| | Credit Card | 3.99% | + R$0.40 per tx |
| | Debit Card | 2.49% | + R$0.40 per tx |
| **Mercado Pago** | Pix | 0.99% | Min R$0.99 |
| | Boleto | R$3.99 | flat |
| | Credit Card | 3.99% | + R$0.40 per tx |
| | Debit Card | 2.49% | + R$0.40 per tx |
| **Stripe** | Pix | 0.8% | Min R$0.59 |
| | Boleto | 0.8% | Min R$0.59 |
| | Credit Card | 3.99% | + R$0.39 per tx |
| | Debit Card | 3.99% | + R$0.39 per tx |

**Note**: Fees are illustrative. Actual fees negotiated per volume. Stripe has lowest Pix rates; Asaas has flat boleto fee advantage.

### Fee Calculator

```typescript
class FeeCalculator {
  calculateFee(provider: ProviderEnum, amount: number, method: PaymentMethod): FeeBreakdown {
    const rates = FEE_TABLE[provider][method];
    let fee: number;

    if (rates.flat) {
      fee = rates.flat;
    } else {
      fee = Math.max(amount * rates.percentage, rates.min || 0);
      fee += rates.perTx || 0;
    }

    return {
      gatewayFee: fee,
      antifraudFee: method === 'credit_card' ? this.getAntifraudFee(provider) : 0,
      iofFee: 0,  // IOF applies only to international cards
      netAmount: amount - fee
    };
  }
}
```

---

## 11. API Endpoints

### Create Payment

```
POST /api/payments
```

```typescript
// Request
{
  provider: 'asaas',           // enum
  amount: 10000,               // cents
  method: 'pix',               // pix | boleto | credit_card | debit_card
  description: 'Invoice #1234',
  externalId: 'ext_1234',      // idempotency key
  customer: {
    name: 'Davi Silva',
    email: 'davi@l2systems.com.br',
    taxId: '123.456.789-00',
    phone: '11999999999'
  },
  metadata: { invoiceId: 'inv_001' },
  dueDate: '2026-07-15',       // optional, boleto
  installments: 3              // optional, card
}

// Response 201
{
  id: 'pay_xxx',
  provider: 'asaas',
  providerPaymentId: 'pay_asaas_xxx',
  status: 'pending',
  amount: 10000,
  fee: 99,
  netAmount: 9901,
  pixQrCode: 'data:image/png;base64,...',
  pixCopyPaste: '00020126580014br.gov.bcb...',
  expiresAt: '2026-07-15T23:59:59Z'
}
```

### List Payments

```
GET /api/payments?provider=asaas&status=approved&method=pix&page=1&limit=50
```

### Get Payment

```
GET /api/payments/:id
```

### Refund Payment

```
POST /api/payments/:id/refund
```

```typescript
// Request (optional body for partial refund)
{ amount: 5000 }  // partial refund, cents
```

### List Providers

```
GET /api/payments/providers
```

```typescript
// Response
[
  { id: 'asaas', name: 'Asaas', status: 'active', methods: ['pix', 'boleto', 'credit_card', 'debit_card'] },
  { id: 'pagseguro', name: 'PagSeguro', status: 'active', methods: ['pix', 'boleto', 'credit_card'] },
  { id: 'mercadopago', name: 'Mercado Pago', status: 'inactive', methods: [] },
  { id: 'stripe', name: 'Stripe Brasil', status: 'active', methods: ['pix', 'boleto', 'credit_card'] }
]
```

### Configure Provider

```
PUT /api/payments/providers/:provider
```

```typescript
// Request
{
  apiKey: 'sk_xxx',
  environment: 'sandbox' | 'production',
  webhookSecret: 'whsec_xxx',
  metadata: { sellerId: 'mp_xxx' }
}
```

### View Fees

```
GET /api/payments/fees?provider=asaas&amount=10000&method=pix
```

```typescript
// Response
{
  gatewayFee: 99,
  antifraudFee: 0,
  iofFee: 0,
  netAmount: 9901,
  effectiveRate: '0.99%'
}
```

### Webhook Receiver

```
POST /api/webhooks/payments/:provider

# Asaas: POST /api/webhooks/payments/asaas
# PagSeguro: POST /api/webhooks/payments/pagseguro
# Mercado Pago: POST /api/webhooks/payments/mercadopago
# Stripe: POST /api/webhooks/payments/stripe
```

---

## 12. Database Schema

```sql
CREATE TABLE payment_providers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  api_key_encrypted TEXT NOT NULL,
  environment TEXT DEFAULT 'sandbox',
  webhook_secret_encrypted TEXT,
  is_active INTEGER DEFAULT 0,
  config JSONB DEFAULT '{}',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE payments (
  id TEXT PRIMARY KEY,
  external_id TEXT UNIQUE NOT NULL,
  provider TEXT NOT NULL REFERENCES payment_providers(id),
  provider_payment_id TEXT,
  customer_id TEXT,
  amount INTEGER NOT NULL,
  currency TEXT DEFAULT 'BRL',
  method TEXT NOT NULL,
  status TEXT DEFAULT 'pending',
  fee INTEGER DEFAULT 0,
  net_amount INTEGER,
  description TEXT,
  metadata JSONB DEFAULT '{}',
  payment_url TEXT,
  pix_qr_code TEXT,
  pix_copy_paste TEXT,
  boleto_url TEXT,
  boleto_barcode TEXT,
  expires_at DATETIME,
  last_polled_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME
);

CREATE TABLE payment_refunds (
  id TEXT PRIMARY KEY,
  payment_id TEXT NOT NULL REFERENCES payments(id),
  provider_refund_id TEXT,
  amount INTEGER NOT NULL,
  status TEXT DEFAULT 'pending',
  reason TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE payment_subscriptions (
  id TEXT PRIMARY KEY,
  external_id TEXT UNIQUE NOT NULL,
  provider TEXT NOT NULL REFERENCES payment_providers(id),
  provider_subscription_id TEXT,
  customer_id TEXT,
  plan_id TEXT,
  status TEXT DEFAULT 'active',
  amount INTEGER NOT NULL,
  billing_cycle TEXT NOT NULL,
  current_period_start DATETIME,
  current_period_end DATETIME,
  payment_method TEXT,
  retry_count INTEGER DEFAULT 0,
  max_retries INTEGER DEFAULT 3,
  metadata JSONB DEFAULT '{}',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE webhook_events (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  provider_event_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload TEXT NOT NULL,
  status TEXT DEFAULT 'pending',
  processed_at DATETIME,
  error TEXT,
  retry_count INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(provider, provider_event_id)
);

CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_provider ON payments(provider);
CREATE INDEX idx_payments_customer ON payments(customer_id);
CREATE INDEX idx_payments_external_id ON payments(external_id);
CREATE INDEX idx_webhook_events_provider ON webhook_events(provider, provider_event_id);
CREATE INDEX idx_subscriptions_status ON payment_subscriptions(status);
```

---

## 13. Effort Estimate

| Component | Provider | Effort (dev-days) | Notes |
|-----------|----------|-------------------|-------|
| **Common Interface** | all | 5 | Types, adapter contract, factory, DB schema |
| **PaymentService** | all | 5 | Orchestrator, CRUD, validation |
| **Asaas Adapter** | asaas | 4 | API client, payment, boleto, card, Pix, webhooks |
| **PagSeguro Adapter** | pagseguro | 4 | Checkout, boleto, Pix, transparent checkout, webhooks |
| **Mercado Pago Adapter** | mercadopago | 5 | OAuth, payment, Pix, subscriptions, split payments |
| **Stripe Brasil Adapter** | stripe | 5 | PaymentIntent, Checkout, Connect, subscriptions, webhooks |
| **Webhook System** | all | 5 | Router, signature verification, idempotency store, queue |
| **Fee Calculator** | all | 2 | Fee tables, calculation, net amount |
| **Subscription Manager** | all | 4 | Lifecycle, dunning, payment method updater |
| **Polling Fallback** | all | 2 | Poller, reconciliation job |
| **API Endpoints** | all | 4 | REST routes, validation, auth middleware |
| **Database + Migrations** | all | 2 | Schema, indexes, seed data |
| **Testing** | all | 5 | Unit tests for adapters, integration tests, webhook tests |
| **Sandbox Setup** | all | 3 | Test accounts, sandbox configs, CI secrets |
| **Total** | | **55 dev-days** | ~11 weeks for 1 dev, ~3 weeks for 2 devs |

### Priority Order

1. **Phase 1** (14 days): Common interface + Asaas adapter + webhook system + DB
2. **Phase 2** (14 days): Stripe Brasil adapter + PagSeguro adapter + fee calculator
3. **Phase 3** (14 days): Mercado Pago adapter + subscriptions + polling
4. **Phase 4** (13 days): API endpoints + testing + sandbox + documentation

### Dependencies

- Asaas: Requires sandbox account (free signup)
- PagSeguro: Requires sandbox credentials from PagSeguro Dev Portal
- Mercado Pago: Requires developer account + OAuth setup
- Stripe: Requires Stripe account with Brasil activated (sk_test_xxx)

---

## 14. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Provider API changes | Medium | Adapter pattern isolates changes; version pin API clients |
| Webhook delivery failures | High | Polling fallback + reconciliation job |
| Fee structure changes | Low | Centralized fee table, easily updatable |
| PCI compliance for card storage | High | Never store raw card data; use tokenization; Stripe handles for us |
| PIX key management | Low | Defer to providers (Asaas, Stripe manage PIX keys) |
| Rate limiting | Medium | Implement retry with exponential backoff per provider |
| Sandbox vs production drift | Medium | Same adapter code, different config; test in sandbox first |

---

## 15. Future Considerations

- **Open Finance integration** (Batch 3, separate research) for account-to-account payments
- **Additional providers**: Pagar.me, Stone, Gerencianet (now Efí)
- **International payments**: Stripe for USD/EUR, Wire Transfer
- **Crypto payments**: PIX via Lightning Network (BTC)
- **Embedded finance**: White-label payment pages for tenant customization
- **Real-time reconciliation**: WebSocket-based status updates instead of polling
- **Tax integration**: ISS/PIS/COFINS tax calculation on payment fees
