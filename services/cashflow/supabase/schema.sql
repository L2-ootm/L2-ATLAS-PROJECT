-- ==============================================================================
-- L2 CASHFLOW — SUPABASE POSTGRESQL SCHEMA MIGRATION
-- ==============================================================================
-- Este arquivo contém o DDL para criar todas as tabelas e funções RPC
-- (Remote Procedure Calls) necessárias para o L2 Cashflow no Supabase.
-- Cole e execute no SQL Editor do Supabase.
-- ==============================================================================

-- 1. TABLES (Legado & Sistema Base)
CREATE TABLE IF NOT EXISTS client (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  service TEXT NOT NULL,
  monthlyPayment NUMERIC DEFAULT 0,
  startDate TEXT NOT NULL,
  contractMonths INTEGER DEFAULT 0,
  active INTEGER DEFAULT 1,
  phone TEXT,
  notes TEXT,
  createdAt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updatedAt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS expense (
  id TEXT PRIMARY KEY,
  description TEXT NOT NULL,
  amount NUMERIC DEFAULT 0,
  date TEXT NOT NULL,
  category TEXT NOT NULL,
  status TEXT DEFAULT 'pending',
  clientId TEXT,
  notes TEXT,
  createdAt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updatedAt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invoice (
  id TEXT PRIMARY KEY,
  clientId TEXT NOT NULL,
  amount NUMERIC DEFAULT 0,
  dueDate TEXT NOT NULL,
  status TEXT DEFAULT 'pending',
  paymentDate TEXT,
  notes TEXT,
  createdAt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updatedAt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS partner_wallet (
  id TEXT PRIMARY KEY,
  partnerName TEXT NOT NULL,
  balance NUMERIC DEFAULT 0,
  createdAt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updatedAt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS partner_transaction (
  id TEXT PRIMARY KEY,
  walletId TEXT NOT NULL,
  amount NUMERIC NOT NULL,
  type TEXT NOT NULL,
  date TEXT NOT NULL,
  description TEXT NOT NULL,
  createdAt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (walletId) REFERENCES partner_wallet(id) ON DELETE CASCADE
);

-- 2. TABLES (FinOps & AI Operations)
CREATE TABLE IF NOT EXISTS client_accounts (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  legal_name TEXT,
  cnpj TEXT,
  segment TEXT,
  estimated_monthly_revenue_brl NUMERIC DEFAULT 0,
  active_students INTEGER DEFAULT 0,
  total_users INTEGER DEFAULT 0,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contracts (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES client_accounts(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  contract_type TEXT,
  start_date TEXT,
  end_date TEXT,
  setup_fee_brl NUMERIC DEFAULT 0,
  monthly_fee_brl NUMERIC DEFAULT 0,
  min_margin_brl NUMERIC DEFAULT 0,
  ai_budget_target_brl NUMERIC DEFAULT 0,
  ai_budget_warning_brl NUMERIC DEFAULT 0,
  ai_budget_hard_cap_brl NUMERIC DEFAULT 0,
  variable_billing_enabled INTEGER DEFAULT 0,
  status TEXT DEFAULT 'active',
  notes TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS plans (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES client_accounts(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  plan_type TEXT,
  price_brl NUMERIC DEFAULT 0,
  billing_cycle TEXT,
  included_users INTEGER DEFAULT 0,
  included_messages INTEGER DEFAULT 0,
  included_advanced_sessions INTEGER DEFAULT 0,
  included_research_credits INTEGER DEFAULT 0,
  ai_cost_target_per_user_brl NUMERIC DEFAULT 0,
  ai_cost_hard_cap_per_user_brl NUMERIC DEFAULT 0,
  overage_policy TEXT,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS usage_events (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES client_accounts(id) ON DELETE CASCADE,
  user_id TEXT,
  session_id TEXT,
  event_type TEXT NOT NULL,
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
  cost_usd NUMERIC DEFAULT 0,
  cost_brl NUMERIC DEFAULT 0,
  revenue_attributed_brl NUMERIC DEFAULT 0,
  margin_attributed_brl NUMERIC DEFAULT 0,
  metadata_json TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_rate_cards (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  effective_from TEXT,
  input_price_per_1m_usd NUMERIC DEFAULT 0,
  output_price_per_1m_usd NUMERIC DEFAULT 0,
  cache_hit_price_per_1m_usd NUMERIC DEFAULT 0,
  cache_write_price_per_1m_usd NUMERIC DEFAULT 0,
  context_window INTEGER DEFAULT 0,
  supports_tools INTEGER DEFAULT 0,
  supports_caching INTEGER DEFAULT 0,
  supports_json INTEGER DEFAULT 0,
  quality_tier TEXT,
  reliability_score NUMERIC,
  latency_score NUMERIC,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS search_rate_cards (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  product TEXT NOT NULL,
  price_per_1000_requests_usd NUMERIC DEFAULT 0,
  price_per_1m_tokens_usd NUMERIC DEFAULT 0,
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
  cost_brl NUMERIC DEFAULT 0,
  result_quality NUMERIC,
  converted_to_knowledge_pack INTEGER DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS invoice_line_items (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES client_accounts(id) ON DELETE CASCADE,
  contract_id TEXT REFERENCES contracts(id) ON DELETE CASCADE,
  period_start TEXT,
  period_end TEXT,
  category TEXT,
  description TEXT,
  quantity INTEGER DEFAULT 1,
  unit_price_brl NUMERIC DEFAULT 0,
  total_brl NUMERIC DEFAULT 0,
  source TEXT,
  status TEXT DEFAULT 'pending',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS plus_subscriptions (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES client_accounts(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL,
  plan_name TEXT NOT NULL,
  price_brl NUMERIC DEFAULT 0,
  gateway TEXT,
  gateway_subscription_id TEXT,
  started_at TEXT,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS billing_events (
  id TEXT PRIMARY KEY,
  subscription_id TEXT REFERENCES plus_subscriptions(id) ON DELETE SET NULL,
  client_id TEXT NOT NULL REFERENCES client_accounts(id) ON DELETE CASCADE,
  user_id TEXT,
  event_type TEXT NOT NULL,
  amount_brl NUMERIC DEFAULT 0,
  gateway_fee_brl NUMERIC DEFAULT 0,
  net_amount_brl NUMERIC DEFAULT 0,
  l2_share_brl NUMERIC DEFAULT 0,
  client_share_brl NUMERIC DEFAULT 0,
  gateway_transaction_id TEXT,
  period_start TEXT,
  period_end TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- 3. RPC FUNCTIONS (Supabase Server-Side aggregations)
-- ==============================================================================

-- A) get_cost_explorer_metrics
CREATE OR REPLACE FUNCTION get_cost_explorer_metrics(p_client_id TEXT, p_month_prefix TEXT)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
  v_cost_by_model JSONB;
  v_top_users JSONB;
  v_cache_tokens JSONB;
BEGIN
  -- Custo por Modelo
  SELECT COALESCE(jsonb_agg(row_to_json(t)), '[]'::jsonb) INTO v_cost_by_model
  FROM (
    SELECT model_name, SUM(cost_brl) as total_cost, SUM(input_tokens) as total_input, SUM(output_tokens) as total_output
    FROM usage_events
    WHERE client_id = p_client_id AND to_char(created_at, 'YYYY-MM') = p_month_prefix AND model_name IS NOT NULL
    GROUP BY model_name
    ORDER BY total_cost DESC
  ) t;

  -- Top 10 Usuários
  SELECT COALESCE(jsonb_agg(row_to_json(t)), '[]'::jsonb) INTO v_top_users
  FROM (
    SELECT user_id, SUM(cost_brl) as total_cost, SUM(input_tokens + output_tokens) as total_tokens, COUNT(id) as total_events
    FROM usage_events
    WHERE client_id = p_client_id AND to_char(created_at, 'YYYY-MM') = p_month_prefix AND user_id IS NOT NULL
    GROUP BY user_id
    ORDER BY total_cost DESC
    LIMIT 10
  ) t;

  -- Cache Hit vs Miss
  SELECT row_to_json(t)::jsonb INTO v_cache_tokens
  FROM (
    SELECT COALESCE(SUM(cache_hit_tokens), 0) as hit, COALESCE(SUM(cache_miss_tokens), 0) as miss
    FROM usage_events
    WHERE client_id = p_client_id AND to_char(created_at, 'YYYY-MM') = p_month_prefix
  ) t;

  RETURN jsonb_build_object(
    'costByModel', v_cost_by_model,
    'topUsers', v_top_users,
    'cacheTokens', v_cache_tokens
  );
END;
$$;

-- B) get_client_pnl
CREATE OR REPLACE FUNCTION get_client_pnl(p_client_id TEXT, p_month_prefix TEXT)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
  v_client JSONB;
  v_contract JSONB;
  v_metrics JSONB;
  v_contract_revenue NUMERIC;
BEGIN
  SELECT row_to_json(client_accounts)::jsonb INTO v_client FROM client_accounts WHERE id = p_client_id;
  SELECT row_to_json(contracts)::jsonb INTO v_contract FROM contracts WHERE client_id = p_client_id AND status = 'active' ORDER BY created_at DESC LIMIT 1;

  v_contract_revenue := COALESCE((v_contract->>'monthly_fee_brl')::numeric, 0);

  SELECT row_to_json(t)::jsonb INTO v_metrics
  FROM (
    SELECT
      COALESCE(SUM(cost_brl), 0) as total_ai_cost_brl,
      COALESCE(SUM(cost_usd), 0) as total_ai_cost_usd,
      COALESCE(SUM(input_tokens), 0) as total_input_tokens,
      COALESCE(SUM(output_tokens), 0) as total_output_tokens,
      COALESCE(SUM(search_requests), 0) as total_search_requests
    FROM usage_events
    WHERE client_id = p_client_id AND to_char(created_at, 'YYYY-MM') = p_month_prefix
  ) t;

  RETURN jsonb_build_object(
    'client', v_client,
    'contract', v_contract,
    'metrics', jsonb_build_object(
      'contracted_revenue', v_contract_revenue,
      'ai_cost', (v_metrics->>'total_ai_cost_brl')::numeric,
      'search_cost', 0,
      'infra_cost', 0,
      'margin', v_contract_revenue - (v_metrics->>'total_ai_cost_brl')::numeric,
      'margin_percentage', CASE WHEN v_contract_revenue > 0 THEN ((v_contract_revenue - (v_metrics->>'total_ai_cost_brl')::numeric) / v_contract_revenue) * 100 ELSE 0 END,
      'total_input_tokens', (v_metrics->>'total_input_tokens')::numeric,
      'total_output_tokens', (v_metrics->>'total_output_tokens')::numeric,
      'total_search_requests', (v_metrics->>'total_search_requests')::numeric
    )
  );
END;
$$;

-- C) get_billing_metrics
CREATE OR REPLACE FUNCTION get_billing_metrics(p_client_id TEXT, p_month_prefix TEXT)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
  v_subs JSONB;
  v_totals JSONB;
  v_recent JSONB;
BEGIN
  SELECT COALESCE(jsonb_agg(row_to_json(t)), '[]'::jsonb) INTO v_subs
  FROM (SELECT * FROM plus_subscriptions WHERE client_id = p_client_id AND status = 'active' ORDER BY created_at DESC) t;

  SELECT row_to_json(t)::jsonb INTO v_totals
  FROM (
    SELECT
      COALESCE(SUM(amount_brl), 0) as gross_revenue,
      COALESCE(SUM(gateway_fee_brl), 0) as total_gateway_fees,
      COALESCE(SUM(net_amount_brl), 0) as total_net,
      COALESCE(SUM(l2_share_brl), 0) as total_l2_share,
      COALESCE(SUM(client_share_brl), 0) as total_client_share,
      COUNT(id) as total_events
    FROM billing_events
    WHERE client_id = p_client_id AND event_type = 'payment_received' AND to_char(created_at, 'YYYY-MM') = p_month_prefix
  ) t;

  SELECT COALESCE(jsonb_agg(row_to_json(t)), '[]'::jsonb) INTO v_recent
  FROM (SELECT * FROM billing_events WHERE client_id = p_client_id AND to_char(created_at, 'YYYY-MM') = p_month_prefix ORDER BY created_at DESC LIMIT 50) t;

  RETURN jsonb_build_object(
    'activeSubscriptions', v_subs,
    'totals', v_totals,
    'recentEvents', v_recent
  );
END;
$$;

-- D) get_forecast_data
CREATE OR REPLACE FUNCTION get_forecast_data(p_client_id TEXT, p_month_prefix TEXT)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
  v_contract JSONB;
  v_cost JSONB;
BEGIN
  SELECT row_to_json(contracts)::jsonb INTO v_contract FROM contracts WHERE client_id = p_client_id AND status = 'active' ORDER BY created_at DESC LIMIT 1;

  SELECT row_to_json(t)::jsonb INTO v_cost
  FROM (
    SELECT COALESCE(SUM(cost_brl), 0) as total_cost, COUNT(DISTINCT to_char(created_at, 'DD')) as active_days
    FROM usage_events
    WHERE client_id = p_client_id AND to_char(created_at, 'YYYY-MM') = p_month_prefix
  ) t;

  RETURN jsonb_build_object(
    'contract', v_contract,
    'cost_data', v_cost
  );
END;
$$;

-- E) get_operational_report
CREATE OR REPLACE FUNCTION get_operational_report(p_client_id TEXT, p_month_prefix TEXT)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
  v_model_breakdown JSONB;
  v_top_users JSONB;
  v_totals JSONB;
  v_cache JSONB;
BEGIN
  SELECT COALESCE(jsonb_agg(row_to_json(t)), '[]'::jsonb) INTO v_model_breakdown
  FROM (
    SELECT model_name, COUNT(id) as sessions, SUM(input_tokens) as input_tokens, SUM(output_tokens) as output_tokens, SUM(cost_brl) as cost
    FROM usage_events WHERE client_id = p_client_id AND to_char(created_at, 'YYYY-MM') = p_month_prefix AND model_name IS NOT NULL
    GROUP BY model_name ORDER BY cost DESC
  ) t;

  SELECT COALESCE(jsonb_agg(row_to_json(t)), '[]'::jsonb) INTO v_top_users
  FROM (
    SELECT user_id, COUNT(id) as sessions, SUM(input_tokens + output_tokens) as tokens, SUM(cost_brl) as cost
    FROM usage_events WHERE client_id = p_client_id AND to_char(created_at, 'YYYY-MM') = p_month_prefix AND user_id IS NOT NULL
    GROUP BY user_id ORDER BY cost DESC LIMIT 10
  ) t;

  SELECT row_to_json(t)::jsonb INTO v_cache
  FROM (
    SELECT COALESCE(SUM(cache_hit_tokens), 0) as hit, COALESCE(SUM(cache_miss_tokens), 0) as miss
    FROM usage_events WHERE client_id = p_client_id AND to_char(created_at, 'YYYY-MM') = p_month_prefix
  ) t;

  SELECT row_to_json(t)::jsonb INTO v_totals
  FROM (
    SELECT COUNT(id) as total_sessions, COALESCE(SUM(input_tokens), 0) as total_input, COALESCE(SUM(output_tokens), 0) as total_output, COALESCE(SUM(cost_brl), 0) as total_cost
    FROM usage_events WHERE client_id = p_client_id AND to_char(created_at, 'YYYY-MM') = p_month_prefix
  ) t;

  RETURN jsonb_build_object(
    'period', p_month_prefix,
    'modelBreakdown', v_model_breakdown,
    'topUsers', v_top_users,
    'cache', v_cache,
    'totals', v_totals
  );
END;
$$;

-- F) get_commercial_report
CREATE OR REPLACE FUNCTION get_commercial_report(p_client_id TEXT, p_month_prefix TEXT)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
  v_client JSONB;
  v_contract JSONB;
  v_plus JSONB;
  v_cost NUMERIC;
  v_students NUMERIC;
  v_subs NUMERIC;
BEGIN
  SELECT row_to_json(client_accounts)::jsonb INTO v_client FROM client_accounts WHERE id = p_client_id;
  SELECT row_to_json(contracts)::jsonb INTO v_contract FROM contracts WHERE client_id = p_client_id AND status = 'active' ORDER BY created_at DESC LIMIT 1;

  SELECT row_to_json(t)::jsonb INTO v_plus
  FROM (
    SELECT COALESCE(SUM(amount_brl), 0) as gross, COALESCE(SUM(net_amount_brl), 0) as net, COALESCE(SUM(l2_share_brl), 0) as l2_share, COALESCE(SUM(client_share_brl), 0) as client_share, COUNT(id) as count
    FROM billing_events WHERE client_id = p_client_id AND event_type = 'payment_received' AND to_char(created_at, 'YYYY-MM') = p_month_prefix
  ) t;

  SELECT COALESCE(SUM(cost_brl), 0) INTO v_cost FROM usage_events WHERE client_id = p_client_id AND to_char(created_at, 'YYYY-MM') = p_month_prefix;
  SELECT COUNT(DISTINCT user_id) INTO v_students FROM usage_events WHERE client_id = p_client_id AND to_char(created_at, 'YYYY-MM') = p_month_prefix;
  SELECT COUNT(id) INTO v_subs FROM plus_subscriptions WHERE client_id = p_client_id AND status = 'active';

  RETURN jsonb_build_object(
    'client', v_client,
    'contract', v_contract,
    'plus', v_plus,
    'total_ai_cost', v_cost,
    'active_students', v_students,
    'active_subs', v_subs
  );
END;
$$;
