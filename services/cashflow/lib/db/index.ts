import Database from 'better-sqlite3';
import path from 'path';

// Specify the path to the database file
const dbPath = path.join(process.cwd(), 'dev.db');
const db = new Database(dbPath);

// Enable performance and foreign keys
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

// Initialize database schema. Additive + NON-DESTRUCTIVE — every statement is
// CREATE TABLE IF NOT EXISTS, so first-time setup never drops or truncates data.
export function initDB() {
    db.exec(`
    CREATE TABLE IF NOT EXISTS Client (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      service TEXT NOT NULL,
      monthlyPayment REAL NOT NULL,
      startDate TEXT NOT NULL,
      contractMonths INTEGER DEFAULT 0,
      active INTEGER DEFAULT 1,
      phone TEXT,
      notes TEXT,
      createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
      updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS Invoice (
      id TEXT PRIMARY KEY,
      clientId TEXT NOT NULL,
      clientName TEXT NOT NULL,
      description TEXT NOT NULL,
      amount REAL NOT NULL,
      issueDate TEXT NOT NULL,
      dueDate TEXT NOT NULL,
      status TEXT DEFAULT 'pendente',
      paidDate TEXT,
      createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
      updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(clientId) REFERENCES Client(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS Expense (
      id TEXT PRIMARY KEY,
      clientId TEXT,
      category TEXT NOT NULL,
      description TEXT NOT NULL,
      amount REAL NOT NULL,
      date TEXT NOT NULL,
      recurring INTEGER DEFAULT 0,
      createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
      updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(clientId) REFERENCES Client(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS Partner (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      role TEXT NOT NULL,
      balance REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS PartnerTransaction (
      id TEXT PRIMARY KEY,
      partnerId TEXT NOT NULL,
      type TEXT NOT NULL,
      amount REAL NOT NULL,
      description TEXT NOT NULL,
      date TEXT NOT NULL,
      createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(partnerId) REFERENCES Partner(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS AITokenLog (
      id TEXT PRIMARY KEY,
      clientId TEXT NOT NULL,
      sourceApp TEXT NOT NULL,
      tokensPrompt INTEGER DEFAULT 0,
      tokensCompletion INTEGER DEFAULT 0,
      model TEXT NOT NULL,
      costUsd REAL NOT NULL,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS client_accounts (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      legal_name TEXT,
      cnpj TEXT,
      segment TEXT,
      estimated_monthly_revenue_brl REAL,
      active_students INTEGER DEFAULT 0,
      total_users INTEGER DEFAULT 0,
      status TEXT DEFAULT 'active',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS contracts (
      id TEXT PRIMARY KEY,
      client_id TEXT NOT NULL,
      name TEXT NOT NULL,
      contract_type TEXT,
      start_date TEXT,
      end_date TEXT,
      setup_fee_brl REAL DEFAULT 0,
      monthly_fee_brl REAL DEFAULT 0,
      min_margin_brl REAL DEFAULT 0,
      ai_budget_target_brl REAL DEFAULT 0,
      ai_budget_warning_brl REAL DEFAULT 0,
      ai_budget_hard_cap_brl REAL DEFAULT 0,
      variable_billing_enabled INTEGER DEFAULT 0,
      status TEXT DEFAULT 'active',
      notes TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(client_id) REFERENCES client_accounts(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS plans (
      id TEXT PRIMARY KEY,
      client_id TEXT NOT NULL,
      name TEXT NOT NULL,
      plan_type TEXT,
      price_brl REAL DEFAULT 0,
      billing_cycle TEXT,
      included_users INTEGER DEFAULT 0,
      included_messages INTEGER DEFAULT 0,
      included_advanced_sessions INTEGER DEFAULT 0,
      included_research_credits INTEGER DEFAULT 0,
      ai_cost_target_per_user_brl REAL DEFAULT 0,
      ai_cost_hard_cap_per_user_brl REAL DEFAULT 0,
      overage_policy TEXT,
      status TEXT DEFAULT 'active',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(client_id) REFERENCES client_accounts(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS user_entitlements (
      id TEXT PRIMARY KEY,
      client_id TEXT NOT NULL,
      external_user_id TEXT,
      internal_user_id TEXT,
      plan TEXT,
      status TEXT DEFAULT 'active',
      valid_until TEXT,
      daily_message_limit INTEGER,
      daily_advanced_limit INTEGER,
      monthly_research_limit INTEGER,
      monthly_ai_budget_brl REAL,
      hard_cap_brl REAL,
      source TEXT,
      external_subscription_id TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(client_id) REFERENCES client_accounts(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS usage_events (
      id TEXT PRIMARY KEY,
      client_id TEXT NOT NULL,
      user_id TEXT,
      session_id TEXT,
      event_type TEXT,
      plan_at_time TEXT,
      route TEXT,
      model_provider TEXT,
      model_name TEXT,
      input_tokens INTEGER DEFAULT 0,
      output_tokens INTEGER DEFAULT 0,
      cache_hit_tokens INTEGER DEFAULT 0,
      cache_miss_tokens INTEGER DEFAULT 0,
      tool_calls INTEGER DEFAULT 0,
      search_requests INTEGER DEFAULT 0,
      retrieval_chunks INTEGER DEFAULT 0,
      cost_usd REAL DEFAULT 0,
      cost_brl REAL DEFAULT 0,
      revenue_attributed_brl REAL DEFAULT 0,
      margin_attributed_brl REAL DEFAULT 0,
      metadata_json TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS model_rate_cards (
      id TEXT PRIMARY KEY,
      provider TEXT NOT NULL,
      model TEXT NOT NULL,
      effective_from TEXT,
      input_price_per_1m_usd REAL DEFAULT 0,
      output_price_per_1m_usd REAL DEFAULT 0,
      cache_hit_price_per_1m_usd REAL DEFAULT 0,
      cache_write_price_per_1m_usd REAL DEFAULT 0,
      context_window INTEGER,
      supports_tools INTEGER DEFAULT 0,
      supports_caching INTEGER DEFAULT 0,
      supports_json INTEGER DEFAULT 0,
      quality_tier TEXT,
      reliability_score REAL,
      latency_score REAL,
      notes TEXT
    );

    CREATE TABLE IF NOT EXISTS search_rate_cards (
      id TEXT PRIMARY KEY,
      provider TEXT NOT NULL,
      product TEXT NOT NULL,
      price_per_1000_requests_usd REAL DEFAULT 0,
      price_per_1m_tokens_usd REAL DEFAULT 0,
      free_quota INTEGER DEFAULT 0,
      quality_tier TEXT,
      notes TEXT
    );

    CREATE TABLE IF NOT EXISTS research_jobs (
      id TEXT PRIMARY KEY,
      client_id TEXT NOT NULL,
      requested_by_user_id TEXT,
      query TEXT NOT NULL,
      normalized_query TEXT,
      topic TEXT,
      priority TEXT DEFAULT 'normal',
      status TEXT DEFAULT 'pending',
      provider_used TEXT,
      cost_brl REAL DEFAULT 0,
      result_quality REAL,
      converted_to_knowledge_pack INTEGER DEFAULT 0,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      completed_at DATETIME
    );

    CREATE TABLE IF NOT EXISTS invoice_line_items (
      id TEXT PRIMARY KEY,
      client_id TEXT NOT NULL,
      contract_id TEXT NOT NULL,
      period_start TEXT,
      period_end TEXT,
      category TEXT,
      description TEXT,
      quantity INTEGER DEFAULT 1,
      unit_price_brl REAL DEFAULT 0,
      total_brl REAL DEFAULT 0,
      source TEXT,
      status TEXT DEFAULT 'pending',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(client_id) REFERENCES client_accounts(id) ON DELETE CASCADE,
      FOREIGN KEY(contract_id) REFERENCES contracts(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS plus_subscriptions (
      id TEXT PRIMARY KEY,
      client_id TEXT NOT NULL,
      user_id TEXT NOT NULL,
      plan_name TEXT NOT NULL,
      price_brl REAL DEFAULT 0,
      status TEXT DEFAULT 'active',
      gateway TEXT,
      gateway_subscription_id TEXT,
      started_at TEXT,
      cancelled_at TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(client_id) REFERENCES client_accounts(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS billing_events (
      id TEXT PRIMARY KEY,
      subscription_id TEXT,
      client_id TEXT NOT NULL,
      user_id TEXT,
      event_type TEXT NOT NULL,
      amount_brl REAL DEFAULT 0,
      gateway_fee_brl REAL DEFAULT 0,
      net_amount_brl REAL DEFAULT 0,
      l2_share_brl REAL DEFAULT 0,
      client_share_brl REAL DEFAULT 0,
      gateway_transaction_id TEXT,
      period_start TEXT,
      period_end TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(client_id) REFERENCES client_accounts(id) ON DELETE CASCADE,
      FOREIGN KEY(subscription_id) REFERENCES plus_subscriptions(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS system_users (
      id TEXT PRIMARY KEY,
      email TEXT UNIQUE NOT NULL,
      name TEXT NOT NULL,
      role TEXT DEFAULT 'viewer',
      password_hash TEXT,
      active INTEGER DEFAULT 1,
      last_login TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS audit_log (
      id TEXT PRIMARY KEY,
      user_id TEXT,
      user_email TEXT,
      action TEXT NOT NULL,
      entity_type TEXT NOT NULL,
      entity_id TEXT,
      details_json TEXT,
      ip_address TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
  `);
}

// Call initDB once at startup
initDB();

export default db;
