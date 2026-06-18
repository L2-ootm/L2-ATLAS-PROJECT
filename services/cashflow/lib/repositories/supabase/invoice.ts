/**
 * Invoice Repository — Supabase Implementation
 */

import { getSupabaseClient } from '../../supabase';
import type { Invoice } from '../../types';
import type { IInvoiceRepository } from '../types';

function rowToInvoice(row: any): Invoice {
  return {
    ...row,
    amount: Number(row.amount),
  };
}

function invoiceToRow(data: Invoice): any {
  return {
    id: data.id,
    clientId: data.clientId,
    clientName: data.clientName,
    description: data.description,
    amount: isNaN(Number(data.amount)) ? 0 : Number(data.amount),
    issueDate: data.issueDate,
    dueDate: data.dueDate,
    paidDate: data.paidDate || null,
    status: data.status,
  };
}

export class SupabaseInvoiceRepository implements IInvoiceRepository {
  async getAll(): Promise<Invoice[]> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('invoice')
      .select('*')
      .order('issueDate', { ascending: false });
      
    if (error) throw error;
    return (data || []).map(rowToInvoice);
  }

  async getById(id: string): Promise<Invoice | null> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('invoice')
      .select('*')
      .eq('id', id)
      .single();
      
    if (error && error.code !== 'PGRST116') throw error;
    return data ? rowToInvoice(data) : null;
  }

  async getByStatus(status: string): Promise<Invoice[]> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('invoice')
      .select('*')
      .eq('status', status)
      .order('dueDate', { ascending: true });
      
    if (error) throw error;
    return (data || []).map(rowToInvoice);
  }

  async getOverdue(): Promise<Invoice[]> {
    const supabase = getSupabaseClient();
    const today = new Date().toISOString().split('T')[0];
    const { data, error } = await supabase
      .from('invoice')
      .select('*')
      .eq('status', 'pending')
      .lt('dueDate', today)
      .order('dueDate', { ascending: true });
      
    if (error) throw error;
    return (data || []).map(rowToInvoice);
  }

  async create(data: Invoice): Promise<Invoice> {
    const supabase = getSupabaseClient();
    const row = invoiceToRow(data);
    
    const { error } = await supabase
      .from('invoice')
      .upsert(row, { onConflict: 'id' });
      
    if (error) throw error;
    return data;
  }

  async update(data: Invoice): Promise<Invoice> {
    const supabase = getSupabaseClient();
    const row = invoiceToRow(data);
    
    const { error } = await supabase
      .from('invoice')
      .update(row)
      .eq('id', data.id);
      
    if (error) throw error;
    return data;
  }

  async delete(id: string): Promise<void> {
    const supabase = getSupabaseClient();
    const { error } = await supabase
      .from('invoice')
      .delete()
      .eq('id', id);
      
    if (error) throw error;
  }
}
