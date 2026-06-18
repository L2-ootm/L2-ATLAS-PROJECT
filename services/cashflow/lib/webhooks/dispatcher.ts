/**
 * Webhook Dispatcher
 * 
 * Responsável por enviar notificações HTTP POST para o L2 Atlas
 * quando eventos relevantes ocorrem no L2-Cashflow.
 * 
 * Configuração via variáveis de ambiente:
 *   L2_ATLAS_WEBHOOK_URL  — URL de destino (ex: https://atlas.l2.com.br/api/webhooks/cashflow)
 *   L2_ATLAS_API_KEY      — Chave de autenticação compartilhada
 */

import type { WebhookEventType, WebhookPayload } from './types';

function generateId(): string {
  return `whk_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Dispara um webhook para o L2 Atlas.
 * 
 * Se a URL não estiver configurada, loga no console e retorna silenciosamente.
 * Nunca lança exceções — falhas de webhook não devem bloquear operações do usuário.
 */
export async function dispatchWebhook(
  event: WebhookEventType,
  data: Record<string, unknown>
): Promise<void> {
  const webhookUrl = process.env.L2_ATLAS_WEBHOOK_URL;
  const apiKey = process.env.L2_ATLAS_API_KEY;

  if (!webhookUrl) {
    console.log(`[Webhook] Skipped (no L2_ATLAS_WEBHOOK_URL configured): ${event}`);
    return;
  }

  const payload: WebhookPayload = {
    id: generateId(),
    timestamp: new Date().toISOString(),
    event,
    source: 'l2-cashflow',
    data,
  };

  try {
    const response = await fetch(webhookUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(apiKey ? { 'Authorization': `Bearer ${apiKey}` } : {}),
        'X-Webhook-Event': event,
        'X-Webhook-Id': payload.id,
        'X-Webhook-Source': 'l2-cashflow',
      },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(10_000), // 10s timeout
    });

    if (!response.ok) {
      console.error(
        `[Webhook] Failed to dispatch "${event}" to ${webhookUrl}: ${response.status} ${response.statusText}`
      );
    } else {
      console.log(`[Webhook] Dispatched "${event}" → ${webhookUrl} (${response.status})`);
    }
  } catch (error) {
    // Fire-and-forget: webhook failures should never block the main operation
    console.error(`[Webhook] Error dispatching "${event}":`, error);
  }
}
