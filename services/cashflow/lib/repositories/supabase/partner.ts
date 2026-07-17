/**
 * Partner Repository — Supabase Implementation
 */

import { getSupabaseClient } from '../../supabase';
import type { PartnerWallet, PartnerTransaction } from '../../types';
import type { IPartnerRepository } from '../types';

function rowToWallet(row: any): PartnerWallet {
  return {
    ...row,
    balance: Number(row.balance),
  };
}

function rowToTransaction(row: any): PartnerTransaction {
  return {
    ...row,
    amount: Number(row.amount),
  };
}

export class SupabasePartnerRepository implements IPartnerRepository {
  async getWallets(): Promise<PartnerWallet[]> {
    const supabase = getSupabaseClient();
    const result = await supabase
      .from('partner_wallet')
      .select('*');
    let data = result.data;

    if (result.error) throw result.error;

    // Seed default wallets if empty (mimicking sqlite behavior)
    if (!data || data.length === 0) {
      await supabase.from('partner_wallet').insert([
        { id: 'partner-a', partnerName: 'Partner A', balance: 0 },
        { id: 'partner-b', partnerName: 'Partner B', balance: 0 }
      ]);
      const res = await supabase.from('partner_wallet').select('*');
      data = res.data;
    }

    return (data || []).map(rowToWallet);
  }

  async getWalletById(id: string): Promise<PartnerWallet | null> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('partner_wallet')
      .select('*')
      .eq('id', id)
      .single();

    if (error && error.code !== 'PGRST116') throw error;
    return data ? rowToWallet(data) : null;
  }

  async updateWalletBalance(walletId: string, amountChange: number): Promise<void> {
    const wallet = await this.getWalletById(walletId);
    if (!wallet) return;

    const supabase = getSupabaseClient();
    const newBalance = wallet.balance + amountChange;

    const { error } = await supabase
      .from('partner_wallet')
      .update({ balance: newBalance })
      .eq('id', walletId);

    if (error) throw error;
  }

  async getTransactions(): Promise<PartnerTransaction[]> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('partner_transaction')
      .select('*')
      .order('date', { ascending: false });

    if (error) throw error;
    return (data || []).map(rowToTransaction);
  }

  async addTransaction(data: PartnerTransaction): Promise<PartnerTransaction> {
    const supabase = getSupabaseClient();

    // Convert to row
    const row = {
      id: data.id,
      walletId: data.partnerId, // Note: SQLite used partnerId, DDL uses walletId. Adapting here.
      type: data.type,
      amount: isNaN(Number(data.amount)) ? 0 : Number(data.amount),
      description: data.description,
      date: data.date,
    };

    const { error } = await supabase
      .from('partner_transaction')
      .upsert(row, { onConflict: 'id' });

    if (error) throw error;
    return data;
  }
}
