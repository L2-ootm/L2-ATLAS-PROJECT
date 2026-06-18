/**
 * Repository Interfaces — Data Access Layer Abstraction
 * 
 * Estas interfaces definem o contrato para acesso a dados.
 * A implementação será usada com Supabase.
 */

import type { Client, Expense, Invoice, PartnerWallet, PartnerTransaction } from '../types';

// ==========================================
// CLIENT REPOSITORY
// ==========================================

export interface IClientRepository {
  getAll(): Promise<Client[]>;
  getActive(): Promise<Client[]>;
  getById(id: string): Promise<Client | null>;
  create(data: Client): Promise<Client>;
  update(data: Client): Promise<Client>;
  delete(id: string): Promise<void>;
}

// ==========================================
// EXPENSE REPOSITORY
// ==========================================

export interface IExpenseRepository {
  getAll(): Promise<Expense[]>;
  getById(id: string): Promise<Expense | null>;
  getByMonth(monthYear: string): Promise<Expense[]>;
  getByClient(clientId: string): Promise<Expense[]>;
  create(data: Expense): Promise<Expense>;
  update(data: Expense): Promise<Expense>;
  delete(id: string): Promise<void>;
}

// ==========================================
// INVOICE REPOSITORY
// ==========================================

export interface IInvoiceRepository {
  getAll(): Promise<Invoice[]>;
  getById(id: string): Promise<Invoice | null>;
  getByStatus(status: string): Promise<Invoice[]>;
  getOverdue(): Promise<Invoice[]>;
  create(data: Invoice): Promise<Invoice>;
  update(data: Invoice): Promise<Invoice>;
  delete(id: string): Promise<void>;
}

// ==========================================
// PARTNER REPOSITORY
// ==========================================

export interface IPartnerRepository {
  getWallets(): Promise<PartnerWallet[]>;
  getWalletById(id: string): Promise<PartnerWallet | null>;
  updateWalletBalance(walletId: string, amountChange: number): Promise<void>;
  getTransactions(): Promise<PartnerTransaction[]>;
  addTransaction(data: PartnerTransaction): Promise<PartnerTransaction>;
}

// ==========================================
// USAGE / AI REPOSITORY
// ==========================================

export interface UsageEvent {
  id: string;
  client_id: string;
  user_id?: string | null;
  session_id?: string | null;
  event_type: string;
  plan_at_time?: string | null;
  route?: string | null;
  model_provider?: string | null;
  model_name?: string | null;
  input_tokens: number;
  output_tokens: number;
  cache_hit_tokens: number;
  cache_miss_tokens: number;
  tool_calls: number;
  search_requests: number;
  retrieval_chunks: number;
  cost_usd: number;
  cost_brl: number;
  revenue_attributed_brl: number;
  margin_attributed_brl: number;
  metadata_json?: string | null;
  created_at?: string;
}

export interface IUsageRepository {
  getAll(limit?: number): Promise<UsageEvent[]>;
  getByClient(clientId: string, limit?: number): Promise<UsageEvent[]>;
  log(data: UsageEvent): Promise<void>;
}

// ==========================================
// RESEARCH REPOSITORY
// ==========================================

export interface ResearchJob {
  id: string;
  client_id: string;
  requested_by_user_id?: string;
  query: string;
  normalized_query?: string;
  topic?: string;
  priority: 'low' | 'normal' | 'high';
  status: 'pending' | 'completed' | 'failed';
  provider_used?: string;
  cost_brl: number;
  result_quality?: number;
  converted_to_knowledge_pack: boolean;
  created_at: string;
  completed_at?: string;
}

export interface IResearchRepository {
  create(job: Partial<ResearchJob>): Promise<ResearchJob>;
  updateStatus(id: string, status: string, costBrl?: number): Promise<void>;
  markAsKnowledgePack(id: string): Promise<void>;
  getJobsByClient(clientId: string): Promise<ResearchJob[]>;
  getJobById(id: string): Promise<ResearchJob | null>;
  getAll(): Promise<ResearchJob[]>;
  getROIStats(clientId: string): Promise<{ totalSpent: number, packsCreated: number, estimatedSavings: number }>;
}
