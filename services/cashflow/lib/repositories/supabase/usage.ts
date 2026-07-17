/**
 * Usage Repository — Supabase Implementation
 */

import { getSupabaseClient } from '../../supabase';
import type { UsageEvent, IUsageRepository } from '../types';

export class SupabaseUsageRepository implements IUsageRepository {
  async getAll(limit: number = 500): Promise<UsageEvent[]> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('usage_events')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(limit);

    if (error) throw error;
    return data as UsageEvent[];
  }

  async getByClient(clientId: string, limit: number = 100): Promise<UsageEvent[]> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('usage_events')
      .select('*')
      .eq('client_id', clientId)
      .order('created_at', { ascending: false })
      .limit(limit);

    if (error) throw error;
    return data as UsageEvent[];
  }

  async log(data: UsageEvent): Promise<void> {
    const supabase = getSupabaseClient();
    const { error } = await supabase
      .from('usage_events')
      .insert([data]);

    if (error) throw error;
  }
}
