/**
 * Research Repository — local SQLite implementation (better-sqlite3).
 */
import db from '../../db';
import type { ResearchJob, IResearchRepository } from '../types';

function rowToJob(row: any): ResearchJob {
  return {
    ...row,
    converted_to_knowledge_pack:
      row.converted_to_knowledge_pack === 1 || row.converted_to_knowledge_pack === true,
  } as ResearchJob;
}

export class SqliteResearchRepository implements IResearchRepository {
  async getAll(): Promise<ResearchJob[]> {
    return (db.prepare('SELECT * FROM research_jobs ORDER BY created_at DESC').all() as any[]).map(rowToJob);
  }

  async getJobsByClient(clientId: string): Promise<ResearchJob[]> {
    return (db
      .prepare('SELECT * FROM research_jobs WHERE client_id = ? ORDER BY created_at DESC')
      .all(clientId) as any[]).map(rowToJob);
  }

  async getJobById(id: string): Promise<ResearchJob | null> {
    const row = db.prepare('SELECT * FROM research_jobs WHERE id = ?').get(id);
    return row ? rowToJob(row) : null;
  }

  async create(job: Partial<ResearchJob>): Promise<ResearchJob> {
    const newJob: ResearchJob = {
      id: job.id || crypto.randomUUID(),
      client_id: job.client_id!,
      requested_by_user_id: job.requested_by_user_id,
      query: job.query!,
      normalized_query: job.normalized_query,
      topic: job.topic,
      priority: job.priority || 'normal',
      status: job.status || 'pending',
      provider_used: job.provider_used,
      cost_brl: job.cost_brl ?? 0,
      result_quality: job.result_quality,
      converted_to_knowledge_pack: job.converted_to_knowledge_pack ?? false,
      created_at: job.created_at || new Date().toISOString(),
      completed_at: job.completed_at,
    };
    db
      .prepare(
        `INSERT INTO research_jobs
          (id, client_id, requested_by_user_id, query, normalized_query, topic, priority, status,
           provider_used, cost_brl, result_quality, converted_to_knowledge_pack, created_at, completed_at)
         VALUES
          (@id, @client_id, @requested_by_user_id, @query, @normalized_query, @topic, @priority, @status,
           @provider_used, @cost_brl, @result_quality, @converted_to_knowledge_pack, @created_at, @completed_at)`
      )
      .run({
        id: newJob.id,
        client_id: newJob.client_id,
        requested_by_user_id: newJob.requested_by_user_id ?? null,
        query: newJob.query,
        normalized_query: newJob.normalized_query ?? null,
        topic: newJob.topic ?? null,
        priority: newJob.priority,
        status: newJob.status,
        provider_used: newJob.provider_used ?? null,
        cost_brl: newJob.cost_brl ?? 0,
        result_quality: newJob.result_quality ?? null,
        converted_to_knowledge_pack: newJob.converted_to_knowledge_pack ? 1 : 0,
        created_at: newJob.created_at,
        completed_at: newJob.completed_at ?? null,
      });
    return newJob;
  }

  async updateStatus(id: string, status: string, costBrl?: number): Promise<void> {
    const completedAt = status === 'completed' ? new Date().toISOString() : null;
    if (costBrl !== undefined) {
      db
        .prepare('UPDATE research_jobs SET status=?, cost_brl=?, completed_at=COALESCE(?, completed_at) WHERE id=?')
        .run(status, costBrl, completedAt, id);
    } else {
      db
        .prepare('UPDATE research_jobs SET status=?, completed_at=COALESCE(?, completed_at) WHERE id=?')
        .run(status, completedAt, id);
    }
  }

  async markAsKnowledgePack(id: string): Promise<void> {
    db.prepare('UPDATE research_jobs SET converted_to_knowledge_pack = 1 WHERE id = ?').run(id);
  }

  async getROIStats(
    clientId: string
  ): Promise<{ totalSpent: number; packsCreated: number; estimatedSavings: number }> {
    const jobs = await this.getJobsByClient(clientId);
    let totalSpent = 0;
    let packsCreated = 0;
    for (const job of jobs) {
      totalSpent += job.cost_brl;
      if (job.converted_to_knowledge_pack) packsCreated++;
    }
    // Each knowledge pack is assumed to prevent ~5 similar future searches.
    const avgCostPerSearch = jobs.length > 0 ? totalSpent / jobs.length : 0;
    const estimatedSavings = packsCreated * 5 * avgCostPerSearch;
    return { totalSpent, packsCreated, estimatedSavings };
  }
}
