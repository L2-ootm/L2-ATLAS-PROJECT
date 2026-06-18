import { getSupabaseClient } from '../supabase';
import { dispatchWebhook } from '../webhooks/dispatcher';

export interface EvaluationResult {
  userId: string;
  totalCostBrl: number;
  hardCapBrl: number;
  actionTaken: 'none' | 'degraded' | 'warned';
}

/**
 * Motor de Degradação Ativa
 * Avalia o risco de um aluno com base no consumo atual vs Hard Cap estabelecido no contrato/plano.
 * Dispara webhooks para o roteador (L2 Atlas) rebaixar o modelo ou bloquear features.
 */
export async function evaluateStudentRisk(userId: string, clientId: string): Promise<EvaluationResult> {
  const supabase = getSupabaseClient();

  // 1. Calcular gasto total do usuário no mês atual
  const now = new Date();
  const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
  
  // Since Supabase JS doesn't have a native SUM() builder without RPC, we fetch the cost_brl column for this user
  // For a single user in a month, the row count is manageable to sum in memory.
  const { data, error } = await supabase
    .from('usage_events')
    .select('cost_brl')
    .eq('user_id', userId)
    .eq('client_id', clientId)
    .gte('created_at', startOfMonth);

  if (error) {
    console.error('[DEGRADATION ENGINE] Failed to fetch usage events:', error);
    throw error;
  }

  const totalCostBrl = (data || []).reduce((sum, row) => sum + (Number(row.cost_brl) || 0), 0);

  // 2. Buscar Entitlements do usuário (Mockado para este motor se não existir tabela específica de plano)
  // Na Fase 5 o L2 Cashflow introduziu Billing Plus. Supondo um limite hardcap fixo se não estiver no banco.
  // Vamos usar R$ 35,00 como hard cap para o LeticIA Plus segundo o report.
  const hardCapBrl = 35.00;
  const warningCapBrl = 25.00;

  let actionTaken: 'none' | 'degraded' | 'warned' = 'none';

  // 3. Lógica de Degradação Ativa
  if (totalCostBrl >= hardCapBrl) {
    console.warn(`[DEGRADATION ENGINE] User ${userId} exceeded hard cap (R$ ${totalCostBrl.toFixed(2)}). Triggering degradation.`);
    
    // Envia comando para L2 Atlas / Roteador
    await dispatchWebhook('user.degraded', {
      user_id: userId,
      client_id: clientId,
      reason: 'hard_cap_exceeded',
      metrics: {
        total_cost: totalCostBrl,
        hard_cap: hardCapBrl
      },
      suggested_action: 'force_flash_models_only'
    });
    
    actionTaken = 'degraded';
  } 
  else if (totalCostBrl >= warningCapBrl) {
    console.info(`[DEGRADATION ENGINE] User ${userId} in warning zone (R$ ${totalCostBrl.toFixed(2)}).`);
    
    await dispatchWebhook('budget.warning', {
      user_id: userId,
      client_id: clientId,
      reason: 'warning_cap_reached',
      metrics: {
        total_cost: totalCostBrl,
        warning_cap: warningCapBrl
      }
    });

    actionTaken = 'warned';
  }

  return {
    userId,
    totalCostBrl,
    hardCapBrl,
    actionTaken
  };
}
