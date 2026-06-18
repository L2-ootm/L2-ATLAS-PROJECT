/**
 * Research Repository — Supabase Implementation
 */

import { getSupabaseClient } from '../../supabase';
import type { ResearchJob, IResearchRepository } from '../types';

export class SupabaseResearchRepository implements IResearchRepository {
  async getAll(): Promise<ResearchJob[]> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('research_jobs')
      .select('*')
      .order('created_at', { ascending: false });
      
    if (error) throw error;
    return data as ResearchJob[];
  }

  async getJobsByClient(clientId: string): Promise<ResearchJob[]> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('research_jobs')
      .select('*')
      .eq('client_id', clientId)
      .order('created_at', { ascending: false });
      
    if (error) throw error;
    return data as ResearchJob[];
  }

  async getJobById(id: string): Promise<ResearchJob | null> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('research_jobs')
      .select('*')
      .eq('id', id)
      .single();
      
    if (error && error.code !== 'PGRST116') throw error;
    return data as ResearchJob | null;
  }

  async create(job: Partial<ResearchJob>): Promise<ResearchJob> {
    const supabase = getSupabaseClient();
    const newJob = {
      id: job.id || crypto.randomUUID(),
      client_id: job.client_id!,
      requested_by_user_id: job.requested_by_user_id || null,
      query: job.query!,
      normalized_query: job.normalized_query || null,
      topic: job.topic || null,
      priority: job.priority || 'normal',
      status: job.status || 'pending',
      provider_used: job.provider_used || null,
      cost_brl: job.cost_brl || 0,
      result_quality: job.result_quality || null,
      converted_to_knowledge_pack: job.converted_to_knowledge_pack ? 1 : 0,
      created_at: job.created_at || new Date().toISOString(),
      completed_at: job.completed_at || null
    };

    const { error } = await supabase
      .from('research_jobs')
      .insert([newJob]);
      
    if (error) throw error;
    return newJob as unknown as ResearchJob;
  }

  async updateStatus(id: string, status: string, costBrl?: number): Promise<void> {
    const supabase = getSupabaseClient();
    const updateData: any = { status };
    if (status === 'completed') {
      updateData.completed_at = new Date().toISOString();
    }
    if (costBrl !== undefined) {
      updateData.cost_brl = costBrl;
    }
    
    const { error } = await supabase
      .from('research_jobs')
      .update(updateData)
      .eq('id', id);
      
    if (error) throw error;
  }

  async markAsKnowledgePack(id: string): Promise<void> {
    const supabase = getSupabaseClient();
    const { error } = await supabase
      .from('research_jobs')
      .update({ converted_to_knowledge_pack: 1 })
      .eq('id', id);
      
    if (error) throw error;
  }

  async getROIStats(clientId: string): Promise<{
    totalSpent: number;
    packsCreated: number;
    estimatedSavings: number;
  }> {
    const jobs = await this.getJobsByClient(clientId);
    let totalSpent = 0;
    let packsCreated = 0;
    
    for (const job of jobs) {
      totalSpent += job.cost_brl;
      if (job.converted_to_knowledge_pack) {
        packsCreated++;
      }
    }
    
    // Calcula economia assumindo que cada knowledge pack previne em média 5 buscas futuras parecidas
    const avgCostPerSearch = jobs.length > 0 ? (totalSpent / jobs.length) : 0;
    const estimatedSavings = packsCreated * 5 * avgCostPerSearch;
    
    return {
      totalSpent,
      packsCreated,
      estimatedSavings
    };
  }
}
