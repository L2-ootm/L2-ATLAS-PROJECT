/**
 * Repositories — Barrel Export & Singleton Instances
 *
 * Backend is SELECTABLE at startup (ATLAS Decision 3b / Decision 4): Supabase when
 * configured (NEXT_PUBLIC_SUPABASE_URL + ANON_KEY present), otherwise the local
 * SQLite backend. Set ATLAS_CASHFLOW_DB=local to force SQLite even when Supabase
 * env is present. Both backends apply their schema non-destructively on first use.
 */

import { isSupabaseConfigured } from '../supabase';
import { SupabaseClientRepository } from './supabase/client';
import { SupabaseExpenseRepository } from './supabase/expense';
import { SupabaseInvoiceRepository } from './supabase/invoice';
import { SupabasePartnerRepository } from './supabase/partner';
import { SupabaseUsageRepository } from './supabase/usage';
import { SupabaseResearchRepository } from './supabase/research';
import { SqliteClientRepository } from './sqlite/client';
import { SqliteExpenseRepository } from './sqlite/expense';
import { SqliteInvoiceRepository } from './sqlite/invoice';
import { SqlitePartnerRepository } from './sqlite/partner';
import { SqliteUsageRepository } from './sqlite/usage';
import { SqliteResearchRepository } from './sqlite/research';
import type {
  IClientRepository,
  IExpenseRepository,
  IInvoiceRepository,
  IPartnerRepository,
  IUsageRepository,
  IResearchRepository,
} from './types';

// Export interfaces
export type {
  IClientRepository,
  IExpenseRepository,
  IInvoiceRepository,
  IPartnerRepository,
  IUsageRepository,
  IResearchRepository,
  UsageEvent,
  ResearchJob
} from './types';

// Backend selection: explicit override (ATLAS_CASHFLOW_DB) wins, else auto-detect.
const forced = process.env.ATLAS_CASHFLOW_DB?.toLowerCase();
const useSupabase = forced === 'supabase' || (forced !== 'local' && isSupabaseConfigured());

// Singleton instances — chosen backend.
export const clientRepo: IClientRepository = useSupabase
  ? new SupabaseClientRepository()
  : new SqliteClientRepository();
export const expenseRepo: IExpenseRepository = useSupabase
  ? new SupabaseExpenseRepository()
  : new SqliteExpenseRepository();
export const invoiceRepo: IInvoiceRepository = useSupabase
  ? new SupabaseInvoiceRepository()
  : new SqliteInvoiceRepository();
export const partnerRepo: IPartnerRepository = useSupabase
  ? new SupabasePartnerRepository()
  : new SqlitePartnerRepository();
export const usageRepo: IUsageRepository = useSupabase
  ? new SupabaseUsageRepository()
  : new SqliteUsageRepository();
export const researchRepo: IResearchRepository = useSupabase
  ? new SupabaseResearchRepository()
  : new SqliteResearchRepository();

/** Which data backend is active — surfaced to the UI / ATLAS System page. */
export const activeBackend: 'supabase' | 'local' = useSupabase ? 'supabase' : 'local';

/**
 * Gera um resumo financeiro agregado.
 * Utilizado pela tool get_financial_summary do MCP.
 */
export async function getFinancialSummary() {
  const clients = await clientRepo.getAll();
  const activeClients = clients.filter(c => c.active);
  const expenses = await expenseRepo.getAll();
  const invoices = await invoiceRepo.getAll();

  const now = new Date();
  const currentMonthPrefix = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;

  const monthlyExpenses = expenses
    .filter(e => e.date.startsWith(currentMonthPrefix))
    .reduce((sum, e) => sum + e.amount, 0);

  const monthlyRecurringRevenue = activeClients.reduce((sum, c) => sum + c.monthlyPayment, 0);

  const pendingInvoices = invoices.filter(i => i.status === 'pendente');
  const overdueInvoices = invoices.filter(i => {
    const today = now.toISOString().split('T')[0];
    return i.status === 'pendente' && i.dueDate < today;
  });

  return {
    totalRevenue: monthlyRecurringRevenue,
    totalExpenses: monthlyExpenses,
    netBalance: monthlyRecurringRevenue - monthlyExpenses,
    activeClients: activeClients.length,
    pendingInvoices: pendingInvoices.length,
    overdueInvoices: overdueInvoices.length,
    monthlyRecurringRevenue,
  };
}
