/**
 * Expense Repository — Supabase Implementation
 */

import { getSupabaseClient } from '../../supabase';
import type { Expense } from '../../types';
import type { IExpenseRepository } from '../types';

function rowToExpense(row: any): Expense {
  return {
    ...row,
    recurring: row.recurring === 1 || row.recurring === true,
    amount: Number(row.amount),
  };
}

function expenseToRow(data: Expense): any {
  return {
    id: data.id,
    clientId: data.clientId || null,
    category: data.category,
    description: data.description,
    amount: isNaN(Number(data.amount)) ? 0 : Number(data.amount),
    date: data.date,
    recurring: data.recurring ? 1 : 0,
  };
}

export class SupabaseExpenseRepository implements IExpenseRepository {
  async getAll(): Promise<Expense[]> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('expense')
      .select('*')
      .order('date', { ascending: false });

    if (error) throw error;
    return (data || []).map(rowToExpense);
  }

  async getById(id: string): Promise<Expense | null> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('expense')
      .select('*')
      .eq('id', id)
      .single();

    if (error && error.code !== 'PGRST116') throw error;
    return data ? rowToExpense(data) : null;
  }

  async getByMonth(monthYear: string): Promise<Expense[]> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('expense')
      .select('*')
      .like('date', `${monthYear}%`)
      .order('date', { ascending: false });

    if (error) throw error;
    return (data || []).map(rowToExpense);
  }

  async getByClient(clientId: string): Promise<Expense[]> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('expense')
      .select('*')
      .eq('clientId', clientId)
      .order('date', { ascending: false });

    if (error) throw error;
    return (data || []).map(rowToExpense);
  }

  async create(data: Expense): Promise<Expense> {
    const supabase = getSupabaseClient();
    const row = expenseToRow(data);

    const { error } = await supabase
      .from('expense')
      .upsert(row, { onConflict: 'id' });

    if (error) throw error;
    return data;
  }

  async update(data: Expense): Promise<Expense> {
    const supabase = getSupabaseClient();
    const row = expenseToRow(data);

    const { error } = await supabase
      .from('expense')
      .update(row)
      .eq('id', data.id);

    if (error) throw error;
    return data;
  }

  async delete(id: string): Promise<void> {
    const supabase = getSupabaseClient();
    const { error } = await supabase
      .from('expense')
      .delete()
      .eq('id', id);

    if (error) throw error;
  }
}
