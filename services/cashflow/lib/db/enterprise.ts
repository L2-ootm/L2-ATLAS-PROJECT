import { clientRepo, invoiceRepo, usageRepo } from '../repositories';
import type { UsageEvent } from '../repositories';
import type { Client, Invoice } from '../types';
import { getSupabaseClient, isSupabaseConfigured } from '../supabase';

interface LocalEnterpriseContext {
  client: Client;
  contract: {
    name: string;
    monthly_fee_brl: number;
    min_margin_brl: number;
    ai_budget_target_brl: number;
    ai_budget_warning_brl: number;
    ai_budget_hard_cap_brl: number;
  };
  usage: UsageEvent[];
  invoices: Invoice[];
  period: string;
}

interface ModelCostRow {
  model_name: string;
  total_cost: number;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  sessions: number;
  cost: number;
}

interface UserCostRow {
  user_id: string;
  total_events: number;
  total_tokens: number;
  total_cost: number;
  sessions: number;
  tokens: number;
  cost: number;
}

function monthPrefix(year: number, month: number): string {
  return `${year}-${month.toString().padStart(2, '0')}`;
}

function eventMatchesMonth(event: UsageEvent, period: string): boolean {
  return Boolean(event.created_at?.startsWith(period));
}

async function getLocalEnterpriseContext(
  requestedClientId: string,
  year: number,
  month: number
): Promise<LocalEnterpriseContext> {
  const clients = await clientRepo.getAll();
  const client =
    clients.find((candidate) => candidate.id === requestedClientId) ??
    clients.find((candidate) => candidate.active) ??
    clients[0] ?? {
      id: requestedClientId,
      name: 'Operação local',
      service: 'Cashflow',
      monthlyPayment: 0,
      startDate: `${year}-${month.toString().padStart(2, '0')}-01`,
      active: true,
      notes: '',
    };
  const period = monthPrefix(year, month);
  const clientIds = new Set([requestedClientId, client.id]);
  const usage = (await usageRepo.getAll(500)).filter(
    (event) => clientIds.has(event.client_id) && eventMatchesMonth(event, period)
  );
  const invoices = (await invoiceRepo.getAll()).filter(
    (invoice) =>
      clientIds.has(invoice.clientId) &&
      (invoice.issueDate.startsWith(period) || invoice.paidDate?.startsWith(period))
  );
  const monthlyRevenue = Number(client.monthlyPayment) || 0;

  return {
    client,
    period,
    usage,
    invoices,
    contract: {
      name: client.service || 'Contrato local',
      monthly_fee_brl: monthlyRevenue,
      min_margin_brl: monthlyRevenue * 0.2,
      ai_budget_target_brl: monthlyRevenue * 0.1,
      ai_budget_warning_brl: monthlyRevenue * 0.15,
      ai_budget_hard_cap_brl: monthlyRevenue * 0.2,
    },
  };
}

function summarizeUsage(usage: UsageEvent[]) {
  return usage.reduce(
    (summary, event) => {
      summary.inputTokens += Number(event.input_tokens) || 0;
      summary.outputTokens += Number(event.output_tokens) || 0;
      summary.cacheHit += Number(event.cache_hit_tokens) || 0;
      summary.cacheMiss += Number(event.cache_miss_tokens) || 0;
      summary.cost += Number(event.cost_brl) || 0;
      return summary;
    },
    { inputTokens: 0, outputTokens: 0, cacheHit: 0, cacheMiss: 0, cost: 0 }
  );
}

function groupUsageByModel(usage: UsageEvent[]): ModelCostRow[] {
  const rows = new Map<string, ModelCostRow>();
  for (const event of usage) {
    const name = event.model_name || event.model_provider || 'unknown';
    const row = rows.get(name) ?? {
      model_name: name,
      total_cost: 0,
      total_tokens: 0,
      input_tokens: 0,
      output_tokens: 0,
      sessions: 0,
      cost: 0,
    };
    row.input_tokens += Number(event.input_tokens) || 0;
    row.output_tokens += Number(event.output_tokens) || 0;
    row.total_tokens = row.input_tokens + row.output_tokens;
    row.total_cost += Number(event.cost_brl) || 0;
    row.cost = row.total_cost;
    row.sessions += 1;
    rows.set(name, row);
  }
  return [...rows.values()].sort((left, right) => right.total_cost - left.total_cost);
}

function groupUsageByUser(usage: UsageEvent[]): UserCostRow[] {
  const rows = new Map<string, UserCostRow>();
  for (const event of usage) {
    const userId = event.user_id || 'sem-identificador';
    const row = rows.get(userId) ?? {
      user_id: userId,
      total_events: 0,
      total_tokens: 0,
      total_cost: 0,
      sessions: 0,
      tokens: 0,
      cost: 0,
    };
    row.total_events += 1;
    row.sessions += 1;
    row.total_tokens +=
      (Number(event.input_tokens) || 0) + (Number(event.output_tokens) || 0);
    row.tokens = row.total_tokens;
    row.total_cost += Number(event.cost_brl) || 0;
    row.cost = row.total_cost;
    rows.set(userId, row);
  }
  return [...rows.values()]
    .sort((left, right) => right.total_cost - left.total_cost)
    .slice(0, 10);
}

async function getLocalBillingMetrics(
  clientId: string,
  year: number,
  month: number
) {
  const context = await getLocalEnterpriseContext(clientId, year, month);
  const paidInvoices = context.invoices.filter((invoice) => invoice.status === 'pago');
  const grossRevenue = paidInvoices.reduce((sum, invoice) => sum + invoice.amount, 0);

  return {
    totals: {
      gross_revenue: grossRevenue,
      total_gateway_fees: 0,
      total_net: grossRevenue,
      total_l2_share: grossRevenue,
      total_client_share: 0,
      total_events: paidInvoices.length,
    },
    activeSubscriptions: [],
    recentEvents: paidInvoices.map((invoice) => ({
      id: invoice.id,
      event_type: 'payment_received',
      user_id: invoice.clientName,
      amount_brl: invoice.amount,
      gateway_fee_brl: 0,
      l2_share_brl: invoice.amount,
      client_share_brl: 0,
    })),
  };
}

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
  if (!isSupabaseConfigured()) {
    const context = await getLocalEnterpriseContext(client_id, year, month);
    const totals = summarizeUsage(context.usage);
    const revenue = context.contract.monthly_fee_brl;
    const margin = revenue - totals.cost;
    return {
      client: { name: context.client.name, segment: context.client.service || 'Local' },
      contract: context.contract,
      metrics: {
        contracted_revenue: revenue,
        ai_cost: totals.cost,
        margin,
        margin_percentage: revenue > 0 ? (margin / revenue) * 100 : 0,
        total_input_tokens: totals.inputTokens,
        total_output_tokens: totals.outputTokens,
      },
    };
  }

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
  if (!isSupabaseConfigured()) {
    const context = await getLocalEnterpriseContext(client_id, year, month);
    const totals = summarizeUsage(context.usage);
    return {
      costByModel: groupUsageByModel(context.usage),
      topUsers: groupUsageByUser(context.usage),
      cacheTokens: { hit: totals.cacheHit, miss: totals.cacheMiss },
    };
  }

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
  if (!isSupabaseConfigured()) {
    return getLocalBillingMetrics(client_id, year, month);
  }

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
  if (!isSupabaseConfigured()) {
    const context = await getLocalEnterpriseContext(client_id, year, month);
    const totals = summarizeUsage(context.usage);
    const now = new Date();
    const daysInMonth = new Date(year, month, 0).getDate();
    const daysPassed =
      year === now.getFullYear() && month === now.getMonth() + 1
        ? now.getDate()
        : daysInMonth;
    const dailyAvgCost = daysPassed > 0 ? totals.cost / daysPassed : 0;
    const forecastedMonthlyCost = dailyAvgCost * daysInMonth;
    const monthlyRevenue = context.contract.monthly_fee_brl;
    const forecastedMargin = monthlyRevenue - forecastedMonthlyCost;
    const budgetRef =
      context.contract.ai_budget_hard_cap_brl > 0
        ? context.contract.ai_budget_hard_cap_brl
        : monthlyRevenue;
    const budgetProgress = budgetRef > 0 ? (totals.cost / budgetRef) * 100 : 0;
    let alertStatus: 'green' | 'yellow' | 'red' = 'green';
    if (
      context.contract.ai_budget_hard_cap_brl > 0 &&
      forecastedMonthlyCost >= context.contract.ai_budget_hard_cap_brl
    ) {
      alertStatus = 'red';
    } else if (
      forecastedMonthlyCost >= context.contract.ai_budget_warning_brl ||
      forecastedMargin < context.contract.min_margin_brl
    ) {
      alertStatus = 'yellow';
    }
    return {
      contract: context.contract,
      totalCost: totals.cost,
      dailyAvgCost,
      forecastedMonthlyCost,
      forecastedMargin,
      monthlyRevenue,
      budgetTarget: context.contract.ai_budget_target_brl,
      budgetWarning: context.contract.ai_budget_warning_brl,
      budgetHardCap: context.contract.ai_budget_hard_cap_brl,
      minMargin: context.contract.min_margin_brl,
      alertStatus,
      budgetProgress,
      daysPassed,
      daysInMonth,
    };
  }

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
  if (!isSupabaseConfigured()) {
    const context = await getLocalEnterpriseContext(client_id, year, month);
    const totals = summarizeUsage(context.usage);
    const billing = await getLocalBillingMetrics(client_id, year, month);
    const contractedRevenue = context.contract.monthly_fee_brl;
    const totalRevenue = contractedRevenue + billing.totals.total_l2_share;
    const grossMargin = contractedRevenue - totals.cost;
    const netMargin = totalRevenue - totals.cost;
    return {
      client: { name: context.client.name },
      contract: context.contract,
      period: context.period,
      rows: [
        { label: 'Receita Contratada (Operação)', value: contractedRevenue },
        { label: 'Receita Plus Bruta', value: billing.totals.gross_revenue },
        { label: 'Receita Plus Líquida (L2 Share)', value: billing.totals.total_l2_share },
        { label: 'Repasse ao Cliente (Plus)', value: billing.totals.total_client_share },
        { label: 'Receita Total L2', value: totalRevenue },
        { label: 'Custo IA Total', value: totals.cost },
        { label: 'Margem Bruta (s/ Plus)', value: grossMargin },
        {
          label: 'Margem Bruta %',
          value: contractedRevenue > 0 ? (grossMargin / contractedRevenue) * 100 : 0,
          isPercent: true,
        },
        { label: 'Margem Líquida (c/ Plus)', value: netMargin },
        {
          label: 'Margem Líquida %',
          value: totalRevenue > 0 ? (netMargin / totalRevenue) * 100 : 0,
          isPercent: true,
        },
        { label: 'Alunos Ativos', value: 0, isCount: true },
        { label: 'Assinaturas Plus Ativas', value: 0, isCount: true },
      ],
    };
  }

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
  if (!isSupabaseConfigured()) {
    const context = await getLocalEnterpriseContext(client_id, year, month);
    const totals = summarizeUsage(context.usage);
    const totalSessions = context.usage.length;
    const cacheTotal = totals.cacheHit + totals.cacheMiss;
    return {
      period: context.period,
      summary: {
        totalSessions,
        totalInputTokens: totals.inputTokens,
        totalOutputTokens: totals.outputTokens,
        totalCost: totals.cost,
        avgCostPerSession: totalSessions > 0 ? totals.cost / totalSessions : 0,
        cacheHitRate: cacheTotal > 0 ? (totals.cacheHit / cacheTotal) * 100 : 0,
      },
      modelBreakdown: groupUsageByModel(context.usage),
      topUsers: groupUsageByUser(context.usage),
    };
  }

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
