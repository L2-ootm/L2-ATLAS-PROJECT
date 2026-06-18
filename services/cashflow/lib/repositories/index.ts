/**
 * Repositories — Barrel Export & Singleton Instances
 * 
 * Ponto central para acessar todos os repositórios.
 * Quando migrarmos para Supabase, basta trocar as implementações aqui.
 */

import { SupabaseClientRepository } from './supabase/client';
import { SupabaseExpenseRepository } from './supabase/expense';
import { SupabaseInvoiceRepository } from './supabase/invoice';
import { SupabasePartnerRepository } from './supabase/partner';
import { SupabaseUsageRepository } from './supabase/usage';
import { SupabaseResearchRepository } from './supabase/research';

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

// Singleton instances — Supabase implementations
export const clientRepo = new SupabaseClientRepository();
export const expenseRepo = new SupabaseExpenseRepository();
export const invoiceRepo = new SupabaseInvoiceRepository();
export const partnerRepo = new SupabasePartnerRepository();
export const usageRepo = new SupabaseUsageRepository();
export const researchRepo = new SupabaseResearchRepository();

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
