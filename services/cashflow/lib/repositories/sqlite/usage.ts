/**
 * Usage Repository — local SQLite implementation (better-sqlite3).
 */
import db from '../../db';
import type { UsageEvent, IUsageRepository } from '../types';

export class SqliteUsageRepository implements IUsageRepository {
  async getAll(limit: number = 500): Promise<UsageEvent[]> {
    return db
      .prepare('SELECT * FROM usage_events ORDER BY created_at DESC LIMIT ?')
      .all(limit) as UsageEvent[];
  }

  async getByClient(clientId: string, limit: number = 100): Promise<UsageEvent[]> {
    return db
      .prepare('SELECT * FROM usage_events WHERE client_id = ? ORDER BY created_at DESC LIMIT ?')
      .all(clientId, limit) as UsageEvent[];
  }

  async log(data: UsageEvent): Promise<void> {
    db
      .prepare(
        `INSERT INTO usage_events
          (id, client_id, user_id, session_id, event_type, plan_at_time, route, model_provider, model_name,
           input_tokens, output_tokens, cache_hit_tokens, cache_miss_tokens, tool_calls, search_requests,
           retrieval_chunks, cost_usd, cost_brl, revenue_attributed_brl, margin_attributed_brl,
           metadata_json, created_at)
         VALUES
          (@id, @client_id, @user_id, @session_id, @event_type, @plan_at_time, @route, @model_provider, @model_name,
           @input_tokens, @output_tokens, @cache_hit_tokens, @cache_miss_tokens, @tool_calls, @search_requests,
           @retrieval_chunks, @cost_usd, @cost_brl, @revenue_attributed_brl, @margin_attributed_brl,
           @metadata_json, @created_at)`
      )
      .run({
        id: data.id,
        client_id: data.client_id,
        user_id: data.user_id ?? null,
        session_id: data.session_id ?? null,
        event_type: data.event_type,
        plan_at_time: data.plan_at_time ?? null,
        route: data.route ?? null,
        model_provider: data.model_provider ?? null,
        model_name: data.model_name ?? null,
        input_tokens: data.input_tokens ?? 0,
        output_tokens: data.output_tokens ?? 0,
        cache_hit_tokens: data.cache_hit_tokens ?? 0,
        cache_miss_tokens: data.cache_miss_tokens ?? 0,
        tool_calls: data.tool_calls ?? 0,
        search_requests: data.search_requests ?? 0,
        retrieval_chunks: data.retrieval_chunks ?? 0,
        cost_usd: data.cost_usd ?? 0,
        cost_brl: data.cost_brl ?? 0,
        revenue_attributed_brl: data.revenue_attributed_brl ?? 0,
        margin_attributed_brl: data.margin_attributed_brl ?? 0,
        metadata_json: data.metadata_json ?? null,
        created_at: data.created_at ?? new Date().toISOString(),
      });
  }
}
