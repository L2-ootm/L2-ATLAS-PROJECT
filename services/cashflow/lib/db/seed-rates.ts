import Database from 'better-sqlite3';
import path from 'path';

// Specify the path to the database file
const dbPath = path.join(process.cwd(), 'dev.db');
const db = new Database(dbPath);

console.log("Seeding Rate Cards...");

const modelRates = [
  {
    id: "claude-3-5-sonnet",
    provider: "Anthropic",
    model: "claude-3-5-sonnet-20241022",
    effective_from: new Date().toISOString(),
    input_price_per_1m_usd: 3.0,
    output_price_per_1m_usd: 15.0,
    cache_hit_price_per_1m_usd: 0.3,
    cache_write_price_per_1m_usd: 3.75, // Usually input price + 25% for Anthropic
    context_window: 200000,
    supports_tools: 1,
    supports_caching: 1,
    supports_json: 1,
    quality_tier: "premium",
  },
  {
    id: "gpt-4o",
    provider: "OpenAI",
    model: "gpt-4o",
    effective_from: new Date().toISOString(),
    input_price_per_1m_usd: 2.5,
    output_price_per_1m_usd: 10.0,
    cache_hit_price_per_1m_usd: 1.25, // 50% discount on input
    cache_write_price_per_1m_usd: 2.5,
    context_window: 128000,
    supports_tools: 1,
    supports_caching: 1,
    supports_json: 1,
    quality_tier: "premium",
  },
  {
    id: "gpt-4o-mini",
    provider: "OpenAI",
    model: "gpt-4o-mini",
    effective_from: new Date().toISOString(),
    input_price_per_1m_usd: 0.15,
    output_price_per_1m_usd: 0.60,
    cache_hit_price_per_1m_usd: 0.075,
    cache_write_price_per_1m_usd: 0.15,
    context_window: 128000,
    supports_tools: 1,
    supports_caching: 1,
    supports_json: 1,
    quality_tier: "standard",
  },
  {
    id: "deepseek-coder",
    provider: "DeepSeek",
    model: "deepseek-coder",
    effective_from: new Date().toISOString(),
    input_price_per_1m_usd: 0.14,
    output_price_per_1m_usd: 0.28,
    cache_hit_price_per_1m_usd: 0.014,
    cache_write_price_per_1m_usd: 0.14,
    context_window: 128000,
    supports_tools: 1,
    supports_caching: 1,
    supports_json: 1,
    quality_tier: "standard",
  }
];

const searchRates = [
  {
    id: "tavily-search",
    provider: "Tavily",
    product: "Search API",
    price_per_1000_requests_usd: 5.0,
    price_per_1m_tokens_usd: 0,
    free_quota: 1000,
    quality_tier: "premium",
  },
  {
    id: "perplexity-sonar",
    provider: "Perplexity",
    product: "sonar-pro",
    price_per_1000_requests_usd: 5.0,
    price_per_1m_tokens_usd: 2.0, // Blended estimate per 1M tokens
    free_quota: 0,
    quality_tier: "premium",
  }
];

const insertModel = db.prepare(`
  INSERT OR REPLACE INTO model_rate_cards (
    id, provider, model, effective_from,
    input_price_per_1m_usd, output_price_per_1m_usd,
    cache_hit_price_per_1m_usd, cache_write_price_per_1m_usd,
    context_window, supports_tools, supports_caching, supports_json, quality_tier
  ) VALUES (
    @id, @provider, @model, @effective_from,
    @input_price_per_1m_usd, @output_price_per_1m_usd,
    @cache_hit_price_per_1m_usd, @cache_write_price_per_1m_usd,
    @context_window, @supports_tools, @supports_caching, @supports_json, @quality_tier
  )
`);

const insertSearch = db.prepare(`
  INSERT OR REPLACE INTO search_rate_cards (
    id, provider, product, price_per_1000_requests_usd, price_per_1m_tokens_usd, free_quota, quality_tier
  ) VALUES (
    @id, @provider, @product, @price_per_1000_requests_usd, @price_per_1m_tokens_usd, @free_quota, @quality_tier
  )
`);

db.transaction(() => {
  for (const rate of modelRates) {
    insertModel.run(rate);
  }
  for (const rate of searchRates) {
    insertSearch.run(rate);
  }
})();

console.log("Seeding complete!");
