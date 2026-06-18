import { getClientPnL } from "@/lib/db/enterprise";
import ServerMonthSelector from "@/components/ServerMonthSelector";
import PnLDashboard from "./PnLDashboard";

export default async function EnterprisePnL({
  searchParams
}: {
  searchParams: Promise<{ month?: string; year?: string }>;
}) {
  const params = await searchParams;
  const now = new Date();
  const selectedMonth = params.month ? parseInt(params.month) : now.getMonth() + 1;
  const selectedYear = params.year ? parseInt(params.year) : now.getFullYear();

  const clientId = 'tds-enterprise-001';
  const pnlData = await getClientPnL(clientId, selectedYear, selectedMonth);

  if (!pnlData || !pnlData.client) {
    return (
      <div style={{ padding: 24 }}>
        <h1>Client P&L</h1>
        <p>Cliente não encontrado ou sem dados no banco.</p>
      </div>
    );
  }

  const { client, contract, metrics } = pnlData;
  const daysPassed = now.getDate();
  const daysInMonth = new Date(selectedYear, selectedMonth, 0).getDate();
  const aiCostForecast = daysPassed > 0 ? (metrics.ai_cost / daysPassed) * daysInMonth : 0;
  const minMarginTarget = contract?.min_margin_brl || 0;
  const marginIsHealthy = metrics.margin >= minMarginTarget;

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <header style={{ marginBottom: 32, display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: "#F1F3F6", margin: "0 0 8px 0" }}>Enterprise P&L</h1>
          <p style={{ color: "#9CA3B4", margin: 0, fontSize: 14 }}>
            Análise de Margem para <strong>{client.name}</strong> ({client.segment})
          </p>
        </div>
        <ServerMonthSelector selectedMonth={selectedMonth} selectedYear={selectedYear} />
      </header>

      <PnLDashboard
        client={client}
        contract={contract}
        metrics={metrics}
        aiCostForecast={aiCostForecast}
        minMarginTarget={minMarginTarget}
        marginIsHealthy={marginIsHealthy}
      />
    </div>
  );
}
