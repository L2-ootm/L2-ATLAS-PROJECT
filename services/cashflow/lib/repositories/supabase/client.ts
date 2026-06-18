/**
 * Client Repository — Supabase Implementation
 */

import { getSupabaseClient } from '../../supabase';
import type { Client } from '../../types';
import type { IClientRepository } from '../types';

function rowToClient(row: any): Client {
  return {
    ...row,
    active: row.active === 1 || row.active === true,
    monthlyPayment: Number(row.monthlyPayment),
    contractMonths: row.contractMonths ?? 0,
  };
}

function clientToRow(data: Client): any {
  return {
    id: data.id,
    name: data.name,
    service: data.service,
    monthlyPayment: isNaN(Number(data.monthlyPayment)) ? 0 : Number(data.monthlyPayment),
    startDate: data.startDate,
    contractMonths: typeof data.contractMonths === 'number' ? data.contractMonths : parseInt(String(data.contractMonths)) || 0,
    active: data.active ? 1 : 0,
    phone: data.phone || null,
    notes: data.notes || null,
  };
}

export class SupabaseClientRepository implements IClientRepository {
  async getAll(): Promise<Client[]> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('client')
      .select('*')
      .order('createdAt', { ascending: false });
      
    if (error) throw error;
    return (data || []).map(rowToClient);
  }

  async getActive(): Promise<Client[]> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('client')
      .select('*')
      .eq('active', 1)
      .order('createdAt', { ascending: false });
      
    if (error) throw error;
    return (data || []).map(rowToClient);
  }

  async getById(id: string): Promise<Client | null> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('client')
      .select('*')
      .eq('id', id)
      .single();
      
    if (error && error.code !== 'PGRST116') throw error; // PGRST116 is "no rows returned"
    return data ? rowToClient(data) : null;
  }

  async create(data: Client): Promise<Client> {
    const supabase = getSupabaseClient();
    const row = clientToRow(data);
    
    const { error } = await supabase
      .from('client')
      .upsert(row, { onConflict: 'id' });
      
    if (error) throw error;
    return data;
  }

  async update(data: Client): Promise<Client> {
    const supabase = getSupabaseClient();
    const row = clientToRow(data);
    
    const { error } = await supabase
      .from('client')
      .update(row)
      .eq('id', data.id);
      
    if (error) throw error;
    return data;
  }

  async delete(id: string): Promise<void> {
    const supabase = getSupabaseClient();
    const { error } = await supabase
      .from('client')
      .delete()
      .eq('id', id);
      
    if (error) throw error;
  }
}
