# B4: Analytics/BI — Embedded Intelligence

**Scope**: L2 Cashflow service  
**Date**: 2026-07-10  
**Status**: PLANNING  
**Stack**: Metabase SDK + Cube.js + DuckDB

---

## 1. Architecture Overview

### 1.1 Data Flow

```
SQLite (transactional)
    ↓  CDC / ETL
DuckDB (analytics OLAP)
    ↑
Cube.js (semantic layer, pre-agg, API)
    ↑
Metabase SDK (embedded dashboards, React)
    ↑
Next.js App (embedded panels, custom KPIs, report builder)
```

### 1.2 Why This Stack

| Component | Role | Why |
|-----------|------|-----|
| **DuckDB** | OLAP engine | Embedded, zero-ops, runs inside the Next.js process or as a sidecar. Handles analytical queries over parquet/CSV without a separate DB server. |
| **Cube.js** | Semantic layer | Defines measures/dimensions once, serves via REST/GraphQL. Handles pre-aggregations, caching, multi-tenancy. Decouples business logic from queries. |
| **Metabase SDK** | Embedded dashboards | React component that renders interactive dashboards inside the app. Users build dashboards via Metabase UI, we embed them. SSO auth via JWT. |
| **Next.js** | Host app | Existing shell. All BI surfaces mount under `/enterprise/analytics/*`. |

### 1.3 Deployment Modes

- **Standalone**: Cube.js + DuckDB run as separate services (Docker Compose)
- **Embedded**: DuckDB runs in-process via `duckdb-node` (for single-tenant deployments)
- **Hybrid**: Cube.js sidecar + DuckDB embedded (recommended for L2 Cashflow)

---

## 2. Metabase SDK Integration

### 2.1 Component-Level React Embedding

```tsx
// components/analytics/MetabaseEmbed.tsx
import { MetabaseEmbed } from "@metabase/embedding-sdk-react";

interface DashboardEmbedProps {
  dashboardId: number;
  parameters?: Record<string, string>;
  height?: string;
  theme?: "light" | "night";
}

export function DashboardEmbed({ 
  dashboardId, 
  parameters = {},
  height = "800px",
  theme = "light" 
}: DashboardEmbedProps) {
  return (
    <MetabaseEmbed
      dashboardId={dashboardId}
      parameters={parameters}
      style={{ width: "100%", height }}
      theme={theme}
    />
  );
}
```

**Route integration**:
```
/enterprise/analytics              → Overview dashboard (embedded)
/enterprise/analytics/dashboards   → List of available dashboards
/enterprise/analytics/dashboards/[id] → Single dashboard (embedded)
/enterprise/analytics/kpis         → KPI scorecards (custom React)
/enterprise/analytics/reports      → Report builder
```

### 2.2 Multi-Tenancy

Each tenant (organization) sees only their data. Implemented via Cube.js `securityContext`:

```javascript
// cube.js security context
module.exports = {
  checkAuth: (req) => {
    const token = req.headers.authorization?.split(" ")[1];
    return jwt.verify(token, process.env.JWT_SECRET);
  },
  securityContext: (identity) => ({
    orgId: identity.org_id,
    userId: identity.user_id,
  }),
};
```

**Metabase SSO flow**:
1. Next.js generates a signed JWT with `org_id`, `user_id`, `exp`
2. Passes JWT to `<MetabaseEmbed jwt={token} />`
3. Metabase verifies JWT, creates session, applies collection-level permissions
4. Dashboard data filtered to tenant via Cube.js `securityContext`

### 2.3 SSO Auth

```typescript
// lib/analytics/metabase-auth.ts
import jwt from "jsonwebtoken";

interface MetabaseJWT {
  email: string;
  first_name: string;
  last_name: string;
  org_id: string;
  user_id: string;
  groups: string[]; // Metabase group IDs for RBAC
  exp: number;
}

export function generateMetabaseJWT(user: User): string {
  return jwt.sign(
    {
      email: user.email,
      first_name: user.firstName,
      last_name: user.lastName,
      org_id: user.orgId,
      user_id: user.id,
      groups: mapRolesToMetabaseGroups(user.roles),
      exp: Math.floor(Date.now() / 1000) + 3600, // 1 hour
    },
    process.env.METABASE_SECRET_KEY!,
    { algorithm: "HS256" }
  );
}
```

### 2.4 Metabase Collection Permissions

| Role | Metabase Group | Access |
|------|----------------|--------|
| `admin` | Analytics Admin | All dashboards, can create/edit/delete |
| `manager` | Analytics Editor | Can create dashboards, see all data |
| `viewer` | Analytics Viewer | Read-only dashboards, filtered by org |

---

## 3. Cube.js Semantic Layer

### 3.1 Schema: Financial Data

```javascript
// cube/schema/usage_events.js
cube(`UsageEvents`, {
  sql: `SELECT * FROM usage_events`,

  measures: {
    total_cost: {
      sql: `cost_usd`,
      type: "sum",
      format: "currency",
    },
    total_tokens: {
      sql: `input_tokens + output_tokens + cache_tokens`,
      type: "sum",
    },
    input_tokens: {
      sql: `input_tokens`,
      type: "sum",
    },
    output_tokens: {
      sql: `output_tokens`,
      type: "sum",
    },
    cache_hit_rate: {
      sql: `CASE WHEN (input_tokens + cache_tokens) > 0 
            THEN cache_tokens * 1.0 / (input_tokens + cache_tokens) 
            ELSE 0 END`,
      type: "avg",
      format: "percent",
    },
    event_count: {
      type: "count",
    },
    cost_per_event: {
      sql: `cost_usd`,
      type: "avg",
      format: "currency",
    },
  },

  dimensions: {
    id: {
      sql: `id`,
      type: "number",
      primary_key: true,
    },
    user_id: {
      sql: `user_id`,
      type: "string",
    },
    model: {
      sql: `model`,
      type: "string",
    },
    feature: {
      sql: `feature`,
      type: "string",
    },
    created_at: {
      sql: `created_at`,
      type: "time",
    },
  },

  pre_aggregations: {
    daily_cost_by_model: {
      measures: [total_cost, event_count],
      dimensions: [model],
      time_dimension: created_at,
      granularity: "day",
      refresh_key: { every: "1 hour" },
    },
    monthly_summary: {
      measures: [total_cost, total_tokens, cache_hit_rate, event_count],
      dimensions: [user_id],
      time_dimension: created_at,
      granularity: "month",
      refresh_key: { every: "1 hour" },
    },
  },
});
```

### 3.2 Schema: Contracts & Billing

```javascript
// cube/schema/contracts.js
cube(`Contracts`, {
  sql: `SELECT * FROM contracts`,

  measures: {
    monthly_revenue: {
      sql: `monthly_value`,
      type: "sum",
      format: "currency",
    },
    contract_count: {
      type: "count_distinct",
      sql: `id`,
    },
    avg_contract_value: {
      sql: `monthly_value`,
      type: "avg",
      format: "currency",
    },
    mrr: {
      sql: `monthly_value`,
      type: "sum",
      filters: { status: "active" },
      format: "currency",
    },
  },

  dimensions: {
    id: {
      sql: `id`,
      type: "number",
      primary_key: true,
    },
    client_id: {
      sql: `client_id`,
      type: "string",
    },
    status: {
      sql: `status`,
      type: "string",
    },
    contract_type: {
      sql: `contract_type`,
      type: "string",
    },
    start_date: {
      sql: `start_date`,
      type: "time",
    },
    end_date: {
      sql: `end_date`,
      type: "time",
    },
  },
});
```

### 3.3 Schema: P&L (Profit & Loss)

```javascript
// cube/schema/pnl.js
cube(`PnL`, {
  sql: `SELECT * FROM pnl_view`, // SQL view joining contracts + usage

  measures: {
    revenue: {
      sql: `contract_value`,
      type: "sum",
      format: "currency",
    },
    ai_cost: {
      sql: `ai_cost_usd`,
      type: "sum",
      format: "currency",
    },
    margin: {
      sql: `contract_value - ai_cost_usd`,
      type: "sum",
      format: "currency",
    },
    margin_percent: {
      sql: `CASE WHEN contract_value > 0 
            THEN (contract_value - ai_cost_usd) / contract_value 
            ELSE 0 END`,
      type: "avg",
      format: "percent",
    },
    burn_rate: {
      sql: `ai_cost_usd`,
      type: "sum",
    },
  },

  dimensions: {
    client_name: {
      sql: `client_name`,
      type: "string",
    },
    period: {
      sql: `period`,
      type: "time",
    },
  },

  pre_aggregations: {
    monthly_pnl: {
      measures: [revenue, ai_cost, margin, margin_percent],
      dimensions: [client_name],
      time_dimension: period,
      granularity: "month",
      refresh_key: { every: "1 hour" },
    },
  },
});
```

### 3.4 Pre-Aggregation Strategy

| Pre-Aggregation | Granularity | Refresh | TTL | Priority |
|-----------------|-------------|---------|-----|----------|
| Daily cost by model | day | 1 hour | 90 days | P0 |
| Monthly summary by user | month | 1 hour | 12 months | P0 |
| Monthly P&L by client | month | 1 hour | 12 months | P0 |
| Hourly cost by feature | hour | 15 min | 30 days | P1 |
| Weekly cohort analysis | week | 4 hours | 6 months | P2 |

---

## 4. Dashboard Configuration

### 4.1 JSON Dashboard Schema (Grafana-style)

```json
{
  "id": "executive-overview",
  "title": "Executive Overview",
  "description": "High-level financial health of all clients",
  "refreshInterval": 30,
  "timeRange": { "default": "30d", "options": ["7d", "30d", "90d", "1y"] },
  "panels": [
    {
      "id": "mrr-scorecard",
      "title": "MRR",
      "type": "scorecard",
      "position": { "x": 0, "y": 0, "w": 3, "h": 2 },
      "query": {
        "cube": "PnL",
        "measures": ["revenue"],
        "timeDimension": "period",
        "dateRange": "this month"
      },
      "format": "currency",
      "compareTo": "prev_month",
      "sparkline": true
    },
    {
      "id": "cost-trend",
      "title": "AI Cost Trend",
      "type": "timeseries",
      "position": { "x": 3, "y": 0, "w": 6, "h": 4 },
      "query": {
        "cube": "UsageEvents",
        "measures": ["total_cost"],
        "timeDimension": "created_at",
        "granularity": "day",
        "dateRange": "30d"
      },
      "series": {
        "stack": false,
        "area": true,
        "gradient": true
      }
    },
    {
      "id": "margin-table",
      "title": "Client Margins",
      "type": "table",
      "position": { "x": 0, "y": 4, "w": 9, "h": 4 },
      "query": {
        "cube": "PnL",
        "measures": ["revenue", "ai_cost", "margin_percent"],
        "dimensions": ["client_name"],
        "timeDimension": "period",
        "dateRange": "this month"
      },
      "columns": {
        "margin_percent": { "type": "percent", "thresholds": [{ "value": 0.2, "color": "red" }, { "value": 0.4, "color": "yellow" }] }
      }
    },
    {
      "id": "top-models",
      "title": "Top Models by Cost",
      "type": "pie",
      "position": { "x": 9, "y": 4, "w": 3, "h": 4 },
      "query": {
        "cube": "UsageEvents",
        "measures": ["total_cost"],
        "dimensions": ["model"],
        "timeDimension": "created_at",
        "dateRange": "30d"
      }
    }
  ],
  "variables": {
    "client": { "type": "query", "multi": true, "query": "SELECT DISTINCT client_name FROM PnL" }
  }
}
```

### 4.2 Panel Types

| Panel Type | Description | Use Case |
|------------|-------------|----------|
| `scorecard` | Single big number with comparison | KPIs (MRR, burn rate) |
| `timeseries` | Line/area chart over time | Cost trends, revenue growth |
| `table` | Sortable, filterable data table | Client margins, audit log |
| `pie` / `donut` | Proportional breakdown | Cost by model, revenue by type |
| `bar` | Horizontal/vertical bars | Top N comparisons |
| `heatmap` | Color-intensity matrix | Usage intensity by hour/day |
| `gauge` | Speedometer-style gauge | Budget utilization |
| `map` | Geographic visualization | Client locations (future) |
| `custom` | React component slot | Specialized KPI cards |

### 4.3 Dashboard Storage

Dashboards stored in `dashboard_configs` table:

```sql
CREATE TABLE dashboard_configs (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  config JSON NOT NULL,        -- The JSON schema above
  owner_id UUID REFERENCES users(id),
  org_id UUID NOT NULL,
  is_template BOOLEAN DEFAULT FALSE,
  is_public BOOLEAN DEFAULT FALSE,
  tags TEXT[] DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE dashboard_favorites (
  user_id UUID REFERENCES users(id),
  dashboard_id TEXT REFERENCES dashboard_configs(id),
  PRIMARY KEY (user_id, dashboard_id)
);
```

---

## 5. Financial KPIs

### 5.1 Pre-Built KPI Definitions

| KPI | Formula | Source | Update Frequency |
|-----|---------|--------|------------------|
| **MRR** | SUM(monthly_value) WHERE status='active' | `contracts` | Real-time |
| **Churn Rate** | (churned_mrr / start_mrr) × 100 | `contracts` | Daily |
| **NRR** | ((start_mrr + expansion - contraction - churn) / start_mrr) × 100 | `contracts` | Monthly |
| **LTV** | (ARPA × Gross Margin %) / Churn Rate % | `contracts` + `usage_events` | Monthly |
| **CAC** | (Sales + Marketing Cost) / New Customers | External input + `contracts` | Monthly |
| **LTV:CAC** | LTV / CAC | Calculated | Monthly |
| **Burn Rate** | SUM(cost_usd) per period | `usage_events` | Daily |
| **Runway** | Cash Balance / Monthly Burn Rate | External + `usage_events` | Daily |
| **Gross Margin %** | ((Revenue - COGS) / Revenue) × 100 | `pnl_view` | Real-time |
| **Cache Efficiency** | cache_tokens / (input_tokens + cache_tokens) | `usage_events` | Real-time |

### 5.2 KPI Implementation (React Components)

```tsx
// components/analytics/kpis/KPICard.tsx
interface KPIDefinition {
  id: string;
  label: string;
  formula: string;
  cube: string;
  measures: string[];
  dimensions?: string[];
  timeDimension: string;
  format: "currency" | "percent" | "number";
  comparison?: "prev_period" | "prev_year" | "target";
  thresholds?: { warning: number; critical: number };
}

const KPI_REGISTRY: Record<string, KPIDefinition> = {
  mrr: {
    id: "mrr",
    label: "Monthly Recurring Revenue",
    formula: "SUM(contracts.monthly_value) WHERE status='active'",
    cube: "Contracts",
    measures: ["mrr"],
    timeDimension: "start_date",
    format: "currency",
    comparison: "prev_period",
    thresholds: { warning: 0.9, critical: 0.8 },
  },
  churn: {
    id: "churn",
    label: "Churn Rate",
    formula: "churned_mrr / start_mrr",
    cube: "Contracts",
    measures: ["mrr"],
    dimensions: ["status"],
    timeDimension: "start_date",
    format: "percent",
    comparison: "prev_period",
    thresholds: { warning: 0.05, critical: 0.10 },
  },
  burn_rate: {
    id: "burn_rate",
    label: "AI Burn Rate",
    formula: "SUM(cost_usd) / days_in_period",
    cube: "UsageEvents",
    measures: ["total_cost"],
    timeDimension: "created_at",
    format: "currency",
    comparison: "prev_period",
  },
  runway: {
    id: "runway",
    label: "Runway (months)",
    formula: "cash_balance / monthly_burn_rate",
    cube: "PnL",
    measures: ["ai_cost"],
    timeDimension: "period",
    format: "number",
    thresholds: { warning: 6, critical: 3 },
  },
};
```

### 5.3 KPI API Endpoint

```typescript
// app/api/v1/analytics/kpis/route.ts
export async function GET(req: Request) {
  const user = await requireAuth(req);
  const { kpis, dateRange } = await req.json();
  
  const results = await Promise.all(
    kpis.map(async (kpiId: string) => {
      const def = KPI_REGISTRY[kpiId];
      if (!def) throw new Error(`Unknown KPI: ${kpiId}`);
      
      const data = await cubeQuery({
        cube: def.cube,
        measures: def.measures,
        dimensions: def.dimensions,
        timeDimension: def.timeDimension,
        dateRange,
      });
      
      const previous = await cubeQuery({
        cube: def.cube,
        measures: def.measures,
        dimensions: def.dimensions,
        timeDimension: def.timeDimension,
        dateRange: shiftDateRange(dateRange, -1),
      });
      
      return {
        id: def.id,
        label: def.label,
        current: data[0],
        previous: previous[0],
        change: calculateChange(data[0], previous[0]),
        format: def.format,
        status: evaluateThreshold(data[0], def.thresholds),
      };
    })
  );
  
  return Response.json({ kpis: results });
}
```

---

## 6. Report Builder

### 6.1 Template System

```json
{
  "id": "monthly-client-report",
  "name": "Monthly Client Report",
  "description": "Comprehensive monthly report for a specific client",
  "parameters": [
    { "name": "client_id", "type": "string", "required": true, "label": "Client" },
    { "name": "month", "type": "date", "required": true, "label": "Month", "default": "current" },
    { "name": "format", "type": "select", "options": ["pdf", "xlsx", "csv"], "default": "pdf" }
  ],
  "sections": [
    {
      "title": "Executive Summary",
      "type": "summary",
      "kpis": ["mrr", "burn_rate", "margin_percent"],
      "period": "{{month}}"
    },
    {
      "title": "Usage Breakdown",
      "type": "chart",
      "chartType": "pie",
      "query": {
        "cube": "UsageEvents",
        "measures": ["total_cost"],
        "dimensions": ["model"],
        "filters": { "user_id": "{{client_id}}" },
        "timeDimension": "created_at",
        "dateRange": "{{month}}"
      }
    },
    {
      "title": "Cost Trend",
      "type": "chart",
      "chartType": "timeseries",
      "query": {
        "cube": "UsageEvents",
        "measures": ["total_cost"],
        "filters": { "user_id": "{{client_id}}" },
        "timeDimension": "created_at",
        "granularity": "day",
        "dateRange": "{{month}}"
      }
    },
    {
      "title": "Top Users",
      "type": "table",
      "query": {
        "cube": "UsageEvents",
        "measures": ["total_cost", "event_count"],
        "dimensions": ["user_id"],
        "filters": { "user_id": "{{client_id}}" },
        "timeDimension": "created_at",
        "dateRange": "{{month}}"
      },
      "limit": 10,
      "sortBy": "total_cost",
      "sortOrder": "desc"
    },
    {
      "title": "P&L Statement",
      "type": "table",
      "query": {
        "cube": "PnL",
        "measures": ["revenue", "ai_cost", "margin", "margin_percent"],
        "filters": { "client_name": "{{client_id}}" },
        "timeDimension": "period",
        "dateRange": "{{month}}"
      }
    }
  ]
}
```

### 6.2 Report Generation Pipeline

```typescript
// lib/analytics/report-builder.ts
class ReportBuilder {
  async generate(templateId: string, params: Record<string, any>): Promise<Buffer> {
    const template = await this.loadTemplate(templateId);
    const format = params.format || "pdf";
    
    // 1. Resolve parameters
    const resolved = this.resolveParams(template, params);
    
    // 2. Execute all section queries in parallel
    const sectionData = await Promise.all(
      resolved.sections.map(section => this.executeSectionQuery(section))
    );
    
    // 3. Render based on format
    switch (format) {
      case "pdf":
        return this.renderPDF(resolved, sectionData);
      case "xlsx":
        return this.renderExcel(resolved, sectionData);
      case "csv":
        return this.renderCSV(resolved, sectionData);
    }
  }
  
  private async renderPDF(template: any, data: any[]): Promise<Buffer> {
    const doc = new jsPDF();
    
    // Title page
    doc.setFontSize(24);
    doc.text(template.name, 20, 30);
    doc.setFontSize(12);
    doc.text(`Generated: ${new Date().toISOString()}`, 20, 40);
    
    // Sections
    let y = 60;
    for (let i = 0; i < template.sections.length; i++) {
      const section = template.sections[i];
      const sectionData = data[i];
      
      // Section title
      doc.setFontSize(16);
      doc.text(section.title, 20, y);
      y += 10;
      
      if (section.type === "chart") {
        const chartImage = await this.renderChartToImage(section.chartType, sectionData);
        doc.addImage(chartImage, "PNG", 20, y, 170, 80);
        y += 90;
      } else if (section.type === "table") {
        doc.autoTable({
          startY: y,
          head: [Object.keys(sectionData[0] || {})],
          body: sectionData.map(row => Object.values(row)),
          margin: { left: 20 },
        });
        y = doc.lastAutoTable.finalY + 10;
      }
      
      // Page break if needed
      if (y > 270) {
        doc.addPage();
        y = 20;
      }
    }
    
    return Buffer.from(doc.output("arraybuffer"));
  }
}
```

### 6.3 Scheduled Reports

```sql
CREATE TABLE report_schedules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  template_id TEXT NOT NULL,
  parameters JSON NOT NULL,
  cron_expression TEXT NOT NULL,  -- e.g. "0 9 1 * *" (monthly 1st at 9am)
  recipients JSONB NOT NULL,     -- ["email1@x.com", "email2@x.com"]
  format TEXT DEFAULT 'pdf',
  org_id UUID NOT NULL,
  enabled BOOLEAN DEFAULT TRUE,
  last_run TIMESTAMPTZ,
  next_run TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Scheduler** (via `node-cron` or external cron):
```typescript
// lib/analytics/report-scheduler.ts
import cron from "node-cron";

async function scheduleReports() {
  const schedules = await db.query("SELECT * FROM report_schedules WHERE enabled = true");
  
  for (const schedule of schedules) {
    cron.schedule(schedule.cron_expression, async () => {
      const report = await reportBuilder.generate(schedule.template_id, schedule.parameters);
      
      // Store in report_history
      await db.query(
        `INSERT INTO report_history (schedule_id, format, file_path, status)
         VALUES ($1, $2, $3, 'completed')`,
        [schedule.id, schedule.format, await saveToStorage(report)]
      );
      
      // Notify recipients
      await notifyRecipients(schedule.recipients, schedule.template_id, report);
      
      // Update last_run / next_run
      await db.query(
        `UPDATE report_schedules SET last_run = NOW(), next_run = $1 WHERE id = $2`,
        [computeNextRun(schedule.cron_expression), schedule.id]
      );
    });
  }
}
```

---

## 7. Drill-Down Architecture

### 7.1 Summary → Detail Flow

```
Level 0: KPI Scorecard (MRR: $50K)
  ↓ click
Level 1: Cube.js query → monthly breakdown by client
  ↓ click on client "TDS"
Level 2: Cube.js query → TDS cost breakdown by model
  ↓ click on "GPT-4o"
Level 3: Cube.js query → individual usage_events for TDS + GPT-4o
  ↓ click on event
Level 4: Raw SQL → full journal entry with context
```

### 7.2 Drill-Down Implementation

```tsx
// components/analytics/DrillDown.tsx
interface DrillPath {
  level: number;
  label: string;
  filters: Record<string, any>;
}

function DrillableChart({ onDrill }: { onDrill: (path: DrillPath) => void }) {
  const [drillPath, setDrillPath] = useState<DrillPath[]>([]);
  
  const handleBarClick = (dataPoint: DataPoint) => {
    const newPath = [
      ...drillPath,
      {
        level: drillPath.length + 1,
        label: dataPoint.label,
        filters: { client_name: dataPoint.clientName },
      },
    ];
    setDrillPath(newPath);
    onDrill({
      level: newPath.length,
      label: dataPoint.label,
      filters: newPath.reduce((acc, p) => ({ ...acc, ...p.filters }), {}),
    });
  };
  
  // Breadcrumb navigation
  return (
    <div>
      <Breadcrumb>
        <Crumb onClick={() => setDrillPath([])}>Overview</Crumb>
        {drillPath.map((p, i) => (
          <Crumb key={i} onClick={() => setDrillPath(drillPath.slice(0, i + 1))}>
            {p.label}
          </Crumb>
        ))}
      </Breadcrumb>
      {/* Chart renders based on current drill level */}
      <DrillableChart level={drillPath.length} filters={currentFilters} />
    </div>
  );
}
```

### 7.3 Drill-Down Levels

| Level | Granularity | Data Source | Example |
|-------|-------------|-------------|---------|
| L0 | KPI summary | Cube.js pre-agg | MRR = $50K |
| L1 | By dimension | Cube.js query | MRR by client |
| L2 | Cross-dimension | Cube.js query | TDS cost by model |
| L3 | Event list | Cube.js raw | Individual usage_events |
| L4 | Full record | Direct SQL | Complete journal entry |

---

## 8. Data Export

### 8.1 Export Formats

| Format | Use Case | Library |
|--------|----------|---------|
| **CSV** | Raw data, external tools | Built-in `papaparse` |
| **Excel** | Financial reports, sharing | `xlsx` (SheetJS) |
| **PDF** | Formal reports, printing | `jspdf` + `jspdf-autotable` (already in deps) |

### 8.2 Export API

```typescript
// app/api/v1/analytics/export/route.ts
export async function GET(req: Request) {
  const { format, cube, measures, dimensions, dateRange, filters } = 
    new URL(req.url).searchParams as any;
  
  const data = await cubeQuery({ cube, measures, dimensions, dateRange, filters });
  
  switch (format) {
    case "csv": {
      const csv = unparse(data);
      return new Response(csv, {
        headers: {
          "Content-Type": "text/csv",
          "Content-Disposition": `attachment; filename="export-${Date.now()}.csv"`,
        },
      });
    }
    
    case "xlsx": {
      const wb = new Workbook();
      const ws = wb.addWorksheet("Export");
      ws.columns = Object.keys(data[0] || {}).map(k => ({ header: k, key: k }));
      ws.addRows(data);
      
      const buffer = await wb.xlsx.writeBuffer();
      return new Response(buffer, {
        headers: {
          "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          "Content-Disposition": `attachment; filename="export-${Date.now()}.xlsx"`,
        },
      });
    }
    
    case "pdf": {
      const doc = new jsPDF();
      doc.autoTable({
        head: [Object.keys(data[0] || {})],
        body: data.map(row => Object.values(row)),
      });
      
      return new Response(Buffer.from(doc.output("arraybuffer")), {
        headers: {
          "Content-Type": "application/pdf",
          "Content-Disposition": `attachment; filename="export-${Date.now()}.pdf"`,
        },
      });
    }
  }
}
```

### 8.3 Dashboard Export

Export entire dashboard as multi-page PDF:

```typescript
// Export each panel as a page
async function exportDashboard(dashboardId: string, format: "pdf" | "xlsx") {
  const config = await getDashboardConfig(dashboardId);
  const doc = new jsPDF();
  
  for (const panel of config.panels) {
    const data = await executePanelQuery(panel.query);
    
    if (panel.type === "scorecard") {
      // Title + big number
      doc.setFontSize(18);
      doc.text(panel.title, 20, 30);
      doc.setFontSize(36);
      doc.text(formatValue(data[0], panel.format), 20, 55);
      doc.addPage();
    } else if (panel.type === "timeseries") {
      const chart = await renderChartToImage(panel, data);
      doc.addImage(chart, "PNG", 20, 20, 170, 80);
      doc.addPage();
    } else if (panel.type === "table") {
      doc.autoTable({
        head: [Object.keys(data[0] || {})],
        body: data.map(row => Object.values(row)),
      });
      doc.addPage();
    }
  }
  
  return Buffer.from(doc.output("arraybuffer"));
}
```

---

## 9. Real-Time Updates

### 9.1 WebSocket for Live Dashboards

```typescript
// lib/analytics/websocket.ts
import { WebSocketServer } from "ws";

const wss = new WebSocketServer({ port: 8080 });

const subscriptions = new Map<string, Set<WebSocket>>();

wss.on("connection", (ws, req) => {
  const token = new URL(req.url!, `http://${req.headers.host}`).searchParams.get("token");
  if (!token || !verifyJWT(token)) {
    ws.close(1008, "Unauthorized");
    return;
  }
  
  ws.on("message", (msg) => {
    const { action, dashboardId, params } = JSON.parse(msg.toString());
    
    if (action === "subscribe") {
      const key = `${dashboardId}:${JSON.stringify(params)}`;
      if (!subscriptions.has(key)) subscriptions.set(key, new Set());
      subscriptions.get(key)!.add(ws);
    }
    
    if (action === "unsubscribe") {
      subscriptions.forEach((clients) => clients.delete(ws));
    }
  });
  
  ws.on("close", () => {
    subscriptions.forEach((clients) => clients.delete(ws));
  });
});
```

### 9.2 Polling Strategies

| Scenario | Strategy | Interval |
|----------|----------|----------|
| Active dashboard (user viewing) | WebSocket push | Real-time |
| Dashboard in background tab | Polling (reduced) | 30 seconds |
| KPI scorecards | Polling | 60 seconds |
| Report generation | Event-driven | On completion |
| Cost alerts | Cube.js refresh key | 5 minutes |

### 9.3 Cube.js Cache Invalidation

```javascript
// cube.js config
module.exports = {
  driverFactory: () => new DuckDBDriver({ /* ... */ }),
  preAggregations: {
    refreshKey: {
      every: "1 hour",
      increment: true, // Only refresh new data, not full rebuild
    },
  },
  // Webhook for invalidation
  onSchemaChange: async (events) => {
    if (events.length > 0) {
      await broadcastToSubscribers("schema_changed");
    }
  },
};
```

### 9.4 Live Dashboard Component

```tsx
// components/analytics/LiveDashboard.tsx
function LiveDashboard({ dashboardId }: { dashboardId: string }) {
  const [data, setData] = useState<any>(null);
  const wsRef = useRef<WebSocket | null>(null);
  
  useEffect(() => {
    const ws = new WebSocket(`wss://analytics.l2atlas.com?token=${getToken()}`);
    wsRef.current = ws;
    
    ws.onopen = () => {
      ws.send(JSON.stringify({
        action: "subscribe",
        dashboardId,
        params: {},
      }));
    };
    
    ws.onmessage = (event) => {
      const update = JSON.parse(event.data);
      if (update.type === "data_update") {
        setData(prev => mergeUpdate(prev, update));
      }
    };
    
    return () => ws.close();
  }, [dashboardId]);
  
  // Fallback to polling if WebSocket fails
  useEffect(() => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) {
      const interval = setInterval(async () => {
        const fresh = await fetchDashboardData(dashboardId);
        setData(fresh);
      }, 30000);
      return () => clearInterval(interval);
    }
  }, [dashboardId, data]);
  
  return <DashboardRenderer config={data} />;
}
```

---

## 10. API Endpoints

### 10.1 Endpoint Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/analytics/dashboards` | List all dashboards |
| `GET` | `/api/v1/analytics/dashboards/:id` | Get dashboard config |
| `POST` | `/api/v1/analytics/dashboards` | Create dashboard |
| `PUT` | `/api/v1/analytics/dashboards/:id` | Update dashboard |
| `DELETE` | `/api/v1/analytics/dashboards/:id` | Delete dashboard |
| `GET` | `/api/v1/analytics/kpis` | Get KPI values |
| `GET` | `/api/v1/analytics/kpis/:id` | Get single KPI |
| `POST` | `/api/v1/analytics/query` | Execute Cube.js query |
| `POST` | `/api/v1/analytics/reports/generate` | Generate report |
| `GET` | `/api/v1/analytics/reports/history` | List past reports |
| `GET` | `/api/v1/analytics/export` | Export data (CSV/XLSX/PDF) |
| `POST` | `/api/v1/analytics/drill-down` | Execute drill-down query |
| `GET` | `/api/v1/analytics/schedules` | List report schedules |
| `POST` | `/api/v1/analytics/schedules` | Create report schedule |

### 10.2 API Response Format

```typescript
// Standard response wrapper
interface AnalyticsResponse<T> {
  success: boolean;
  data: T;
  meta: {
    queryTime: number;
    cacheHit: boolean;
    rowCount: number;
  };
  error?: string;
}

// Example: GET /api/v1/analytics/kpis
{
  "success": true,
  "data": {
    "kpis": [
      {
        "id": "mrr",
        "label": "MRR",
        "current": 50000,
        "previous": 48000,
        "change": { "absolute": 2000, "percent": 4.17, "direction": "up" },
        "format": "currency",
        "status": "healthy"
      }
    ]
  },
  "meta": { "queryTime": 45, "cacheHit": true, "rowCount": 1 }
}
```

### 10.3 Rate Limiting

| Endpoint | Limit | Window |
|----------|-------|--------|
| Dashboard list | 100 req/min | Rolling |
| KPI queries | 60 req/min | Rolling |
| Data export | 10 req/min | Rolling |
| Report generation | 5 req/min | Rolling |
| Cube.js raw query | 30 req/min | Rolling |

---

## 11. Integration with Existing L2 Cashflow Features

### 11.1 Mapping to Current Features

| Existing Feature | Analytics Integration |
|------------------|----------------------|
| Enterprise P&L (`/enterprise/pnl`) | Replace with embedded Metabase P&L dashboard |
| AI Cost Explorer (`/enterprise/explorer`) | Replace with Cube.js-backed explorer |
| Forecast (`/enterprise/forecast`) | Add to analytics as forecasting panel |
| Reports (`/enterprise/reports`) | Extend with report builder + scheduling |
| Audit (`/enterprise/audit`) | New audit analytics dashboard |
| Billing Plus splits | New billing analytics dashboard |

### 11.2 Migration Strategy

**Phase 1**: Add Cube.js + DuckDB alongside existing charts
- Existing recharts components continue working
- New analytics pages use Cube.js

**Phase 2**: Replace recharts with Metabase embeds
- Build equivalent dashboards in Metabase
- Swap React components one-by-one

**Phase 3**: Full analytics platform
- Custom KPI scorecards (React)
- Embedded dashboards (Metabase)
- Report builder (custom)
- Export system (shared)

---

## 12. Effort Estimate

| Component | Effort (person-weeks) | Priority | Dependencies |
|-----------|----------------------|----------|--------------|
| **1. Metabase SDK Integration** | 3 | P0 | Metabase server setup |
| React embedding | 1 | | Next.js app |
| SSO auth + JWT | 1 | | JWT library |
| Collection permissions | 1 | | RBAC system |
| **2. Cube.js Semantic Layer** | 4 | P0 | DuckDB setup |
| Schema: UsageEvents | 1 | | DB migrations |
| Schema: Contracts | 1 | | DB migrations |
| Schema: P&L | 1 | | DB migrations |
| Pre-aggregations tuning | 1 | | Performance testing |
| **3. Dashboard Configuration** | 3 | P1 | Cube.js schemas |
| JSON schema definition | 0.5 | | None |
| Panel type implementations | 1.5 | | Recharts/custom |
| Dashboard CRUD API | 1 | | Database schema |
| **4. Financial KPIs** | 2 | P1 | Cube.js schemas |
| KPI definitions (10 KPIs) | 1 | | Business logic |
| KPI React components | 0.5 | | Design system |
| KPI API + caching | 0.5 | | Cache layer |
| **5. Report Builder** | 4 | P1 | jsPDF (existing) |
| Template engine | 1 | | None |
| PDF generation | 1 | | jsPDF, jspdf-autotable |
| Excel generation | 0.5 | | xlsx library |
| Scheduler + notifications | 1.5 | | Cron infrastructure |
| **6. Drill-Down** | 2 | P2 | Cube.js schemas |
| Breadcrumb navigation | 0.5 | | UI components |
| Multi-level queries | 1 | | Cube.js API |
| Journal entry view | 0.5 | | Database schema |
| **7. Data Export** | 2 | P2 | None |
| CSV export | 0.5 | | papaparse |
| Excel export | 0.5 | | xlsx library |
| PDF export | 0.5 | | jsPDF (existing) |
| Dashboard-level export | 0.5 | | All formats |
| **8. Real-Time Updates** | 3 | P2 | WebSocket infra |
| WebSocket server | 1 | | WebSocket library |
| Polling fallback | 0.5 | | None |
| Live dashboard component | 1 | | React state |
| Cache invalidation | 0.5 | | Cube.js config |
| **9. API Endpoints** | 2 | P1 | All components |
| CRUD endpoints | 1 | | Route handlers |
| Rate limiting + validation | 1 | | Middleware |
| **10. Testing & Polish** | 2 | P2 | All components |
| Integration tests | 1 | | Test framework |
| Performance testing | 0.5 | | Load testing |
| Documentation | 0.5 | | None |
| **TOTAL** | **27** | | |

---

## 13. Implementation Timeline

### Phase 1: Foundation (Weeks 1-4)
- Set up DuckDB alongside SQLite
- Deploy Cube.js with DuckDB driver
- Create semantic schemas (UsageEvents, Contracts, P&L)
- Metabase server setup + React embedding

### Phase 2: Core Dashboards (Weeks 5-8)
- Executive overview dashboard
- Client P&L dashboard
- Cost explorer dashboard
- KPI scorecards

### Phase 3: Advanced Features (Weeks 9-12)
- Report builder + PDF/Excel generation
- Drill-down navigation
- Scheduled reports

### Phase 4: Real-Time & Polish (Weeks 13-16)
- WebSocket live updates
- Data export (CSV/Excel/PDF)
- Performance optimization
- Documentation

---

## 14. Dependencies

### New Dependencies (package.json additions)

```json
{
  "@metabase/embedding-sdk-react": "^1.0.0",
  "duckdb": "^1.0.0",
  "cubejs": "^1.0.0",
  "papaparse": "^5.4.0",
  "xlsx": "^0.18.0",
  "ws": "^8.16.0",
  "node-cron": "^3.0.0",
  "jsonwebtoken": "^9.0.0"
}
```

### Infrastructure

| Component | Deployment | Resource |
|-----------|------------|----------|
| DuckDB | Embedded (in-process) or sidecar | < 512MB RAM |
| Cube.js | Docker container | 1 CPU, 1GB RAM |
| Metabase | Docker container | 2 CPU, 4GB RAM |
| WebSocket | Next.js custom server or standalone | < 256MB RAM |

---

## 15. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Dashboard load time | < 2 seconds | Lighthouse |
| KPI query time | < 100ms | Cube.js metrics |
| Export generation | < 5 seconds | API response time |
| WebSocket latency | < 500ms | Server metrics |
| Report generation | < 30 seconds | End-to-end timing |
| Cache hit rate | > 80% | Cube.js metrics |
| User adoption | 80% of managers | Usage analytics |

---

**Next steps**:
1. Set up DuckDB instance and Cube.js server
2. Create initial schemas for UsageEvents and Contracts
3. Deploy Metabase and configure SSO
4. Build executive overview dashboard as proof-of-concept
