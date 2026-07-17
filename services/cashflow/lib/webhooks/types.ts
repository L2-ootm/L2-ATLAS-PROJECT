/**
 * Webhook Event Types
 *
 * Define todos os eventos que o L2-Cashflow pode disparar para o L2 Atlas.
 */

export type WebhookEventType =
  | 'client.created'
  | 'client.updated'
  | 'client.deleted'
  | 'expense.created'
  | 'expense.updated'
  | 'expense.deleted'
  | 'invoice.created'
  | 'invoice.updated'
  | 'invoice.paid'
  | 'invoice.overdue'
  | 'partner.transaction'
  | 'usage.logged'
  | 'budget.warning'
  | 'budget.exceeded'
  | 'user.degraded';

export interface WebhookPayload {
  /** Unique ID for this webhook delivery */
  id: string;
  /** ISO 8601 timestamp */
  timestamp: string;
  /** The event type */
  event: WebhookEventType;
  /** Source application identifier */
  source: 'l2-cashflow';
  /** The event data */
  data: Record<string, unknown>;
}
