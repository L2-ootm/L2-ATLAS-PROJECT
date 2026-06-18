import { getSupabaseClient } from '../supabase';

// ==========================================
// CLIENT ACCOUNTS
// ==========================================

export async function createClientAccount(data: {
  id: string;
  name: string;
  legal_name?: string;
  cnpj?: string;
  segment?: string;
  estimated_monthly_revenue_brl?: number;
  active_students?: number;
  total_users?: number;
}) {
  const supabase = getSupabaseClient();
  const { error } = await supabase.from('client_accounts').insert([data]);
  if (error) throw error;
  return data;
}

export async function getClientAccounts() {
  const supabase = getSupabaseClient();
  const { data, error } = await supabase.from('client_accounts').select('*').order('name', { ascending: true });
  if (error) throw error;
  return data;
}

// ==========================================
// CONTRACTS
// ==========================================

export async function createContract(data: {
  id: string;
  client_id: string;
  name: string;
  contract_type?: string;
  setup_fee_brl?: number;
  monthly_fee_brl?: number;
  min_margin_brl?: number;
}) {
  const supabase = getSupabaseClient();
  const { error } = await supabase.from('contracts').insert([data]);
  if (error) throw error;
  return data;
}

// ==========================================
// USAGE EVENTS
// ==========================================

export async function logUsageEvent(data: any) {
  const supabase = getSupabaseClient();
  const { error } = await supabase.from('usage_events').insert([data]);
  if (error) throw error;
  return data;
}

export async function getClientUsageEvents(client_id: string) {
  const supabase = getSupabaseClient();
  const { data, error } = await supabase
    .from('usage_events')
    .select('*')
    .eq('client_id', client_id)
    .order('created_at', { ascending: false })
    .limit(100);
  if (error) throw error;
  return data;
}

export async function getAllUsageEvents() {
  const supabase = getSupabaseClient();
  const { data, error } = await supabase
    .from('usage_events')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(500);
  if (error) throw error;
  return data;
}

// ==========================================
// P&L AND AGGREGATIONS (RPC CALLS)
// ==========================================

export async function getClientPnL(client_id: string, year: number, month: number) {
  const monthStr = month.toString().padStart(2, '0');
  const monthPrefix = `${year}-${monthStr}`;

  const supabase = getSupabaseClient();
  const { data, error } = await supabase.rpc('get_client_pnl', {
    p_client_id: client_id,
    p_month_prefix: monthPrefix
  });

  if (error) throw error;
  return data;
}

export async function getCostExplorerMetrics(client_id: string, year: number, month: number) {
  const monthStr = month.toString().padStart(2, '0');
  const monthPrefix = `${year}-${monthStr}`;

  const supabase = getSupabaseClient();
  const { data, error } = await supabase.rpc('get_cost_explorer_metrics', {
    p_client_id: client_id,
    p_month_prefix: monthPrefix
  });

  if (error) throw error;
  return data;
}

// ==========================================
// BILLING PLUS (FASE 5)
// ==========================================

export async function createPlusSubscription(data: any) {
  const supabase = getSupabaseClient();
  const { error } = await supabase.from('plus_subscriptions').insert([data]);
  if (error) throw error;
  return data;
}

export async function getPlusSubscriptions(client_id: string) {
  const supabase = getSupabaseClient();
  const { data, error } = await supabase
    .from('plus_subscriptions')
    .select('*')
    .eq('client_id', client_id)
    .order('created_at', { ascending: false });
  if (error) throw error;
  return data;
}

export async function logBillingEvent(data: any) {
  const supabase = getSupabaseClient();
  const { error } = await supabase.from('billing_events').insert([data]);
  if (error) throw error;
  return data;
}

export async function getBillingMetrics(client_id: string, year: number, month: number) {
  const monthStr = month.toString().padStart(2, '0');
  const monthPrefix = `${year}-${monthStr}`;

  const supabase = getSupabaseClient();
  const { data, error } = await supabase.rpc('get_billing_metrics', {
    p_client_id: client_id,
    p_month_prefix: monthPrefix
  });

  if (error) throw error;
  return data;
}

// ==========================================
// FORECAST & SIMULATOR (FASE 6)
// ==========================================

export async function getForecastData(client_id: string, year: number, month: number) {
  const monthStr = month.toString().padStart(2, '0');
  const monthPrefix = `${year}-${monthStr}`;

  const supabase = getSupabaseClient();
  const { data, error } = await supabase.rpc('get_forecast_data', {
    p_client_id: client_id,
    p_month_prefix: monthPrefix
  });

  if (error) throw error;

  // Realizar cálculos de projeção que independem do banco (apenas matemática)
  const contract = data.contract;
  const totalCost = data.cost_data?.total_cost || 0;
  const activeDays = data.cost_data?.active_days || 1;
  const now = new Date();
  const daysInMonth = new Date(year, month, 0).getDate();
  const daysPassed = (year === now.getFullYear() && month === now.getMonth() + 1) ? now.getDate() : daysInMonth;

  const dailyAvgCost = daysPassed > 0 ? totalCost / daysPassed : 0;
  const forecastedMonthlyCost = dailyAvgCost * daysInMonth;

  const budgetTarget = contract?.ai_budget_target_brl || 0;
  const budgetWarning = contract?.ai_budget_warning_brl || 0;
  const budgetHardCap = contract?.ai_budget_hard_cap_brl || 0;
  const monthlyRevenue = contract?.monthly_fee_brl || 0;

  const forecastedMargin = monthlyRevenue - forecastedMonthlyCost;
  const minMargin = contract?.min_margin_brl || 0;

  let alertStatus: 'green' | 'yellow' | 'red' = 'green';
  if (budgetHardCap > 0 && forecastedMonthlyCost >= budgetHardCap) alertStatus = 'red';
  else if (budgetWarning > 0 && forecastedMonthlyCost >= budgetWarning) alertStatus = 'yellow';
  else if (forecastedMargin < minMargin) alertStatus = 'yellow';

  const budgetRef = budgetHardCap > 0 ? budgetHardCap : monthlyRevenue;
  const budgetProgress = budgetRef > 0 ? (totalCost / budgetRef) * 100 : 0;

  return {
    contract,
    totalCost,
    dailyAvgCost,
    forecastedMonthlyCost,
    forecastedMargin,
    monthlyRevenue,
    budgetTarget,
    budgetWarning,
    budgetHardCap,
    minMargin,
    alertStatus,
    budgetProgress,
    daysPassed,
    daysInMonth
  };
}

export function simulateMargin(params: {
  monthlyRevenue: number;
  currentMonthlyCost: number;
  costPerSessionAdjust: number; 
  studentCountAdjust: number;   
  cacheHitRateAdjust: number;   
}) {
  const adjustedCost = params.currentMonthlyCost
    * params.costPerSessionAdjust
    * params.studentCountAdjust
    * params.cacheHitRateAdjust;

  const simulatedMargin = params.monthlyRevenue - adjustedCost;
  const simulatedMarginPct = params.monthlyRevenue > 0
    ? (simulatedMargin / params.monthlyRevenue) * 100
    : 0;

  return {
    adjustedCost,
    simulatedMargin,
    simulatedMarginPct,
    originalCost: params.currentMonthlyCost,
    originalMargin: params.monthlyRevenue - params.currentMonthlyCost
  };
}

// ==========================================
// REPORTS (FASE 7)
// ==========================================

export async function getCommercialReport(client_id: string, year: number, month: number) {
  const monthStr = month.toString().padStart(2, '0');
  const monthPrefix = `${year}-${monthStr}`;

  const supabase = getSupabaseClient();
  const { data, error } = await supabase.rpc('get_commercial_report', {
    p_client_id: client_id,
    p_month_prefix: monthPrefix
  });

  if (error) throw error;

  const contractedRevenue = data.contract?.monthly_fee_brl || 0;
  const totalAiCost = data.total_ai_cost || 0;
  const plusGross = data.plus?.gross || 0;
  const plusL2Share = data.plus?.l2_share || 0;
  const plusClientShare = data.plus?.client_share || 0;

  const grossMargin = contractedRevenue - totalAiCost;
  const grossMarginPct = contractedRevenue > 0 ? (grossMargin / contractedRevenue) * 100 : 0;
  const totalRevenue = contractedRevenue + plusL2Share;
  const netMargin = totalRevenue - totalAiCost;
  const netMarginPct = totalRevenue > 0 ? (netMargin / totalRevenue) * 100 : 0;

  return {
    client: data.client,
    contract: data.contract,
    period: monthPrefix,
    rows: [
      { label: 'Receita Contratada (Operação)', value: contractedRevenue },
      { label: 'Receita Plus Bruta', value: plusGross },
      { label: 'Receita Plus Líquida (L2 Share)', value: plusL2Share },
      { label: 'Repasse ao Cliente (Plus)', value: plusClientShare },
      { label: 'Receita Total L2', value: totalRevenue },
      { label: 'Custo IA Total', value: totalAiCost },
      { label: 'Margem Bruta (s/ Plus)', value: grossMargin },
      { label: 'Margem Bruta %', value: grossMarginPct, isPercent: true },
      { label: 'Margem Líquida (c/ Plus)', value: netMargin },
      { label: 'Margem Líquida %', value: netMarginPct, isPercent: true },
      { label: 'Alunos Ativos', value: data.active_students || 0, isCount: true },
      { label: 'Assinaturas Plus Ativas', value: data.active_subs || 0, isCount: true },
    ]
  };
}

export async function getOperationalReport(client_id: string, year: number, month: number) {
  const monthStr = month.toString().padStart(2, '0');
  const monthPrefix = `${year}-${monthStr}`;

  const supabase = getSupabaseClient();
  const { data, error } = await supabase.rpc('get_operational_report', {
    p_client_id: client_id,
    p_month_prefix: monthPrefix
  });

  if (error) throw error;

  const totalSessions = data.totals?.total_sessions || 0;
  const totalCost = data.totals?.total_cost || 0;
  const avgCostPerSession = totalSessions > 0 ? totalCost / totalSessions : 0;
  
  const cacheHit = data.cache?.hit || 0;
  const cacheMiss = data.cache?.miss || 0;
  const cacheHitRate = (cacheHit + cacheMiss) > 0 ? (cacheHit / (cacheHit + cacheMiss)) * 100 : 0;

  return {
    period: data.period,
    summary: {
      totalSessions,
      totalInputTokens: data.totals?.total_input || 0,
      totalOutputTokens: data.totals?.total_output || 0,
      totalCost,
      avgCostPerSession,
      cacheHitRate
    },
    modelBreakdown: data.modelBreakdown || [],
    topUsers: data.topUsers || []
  };
}
