import { getCostExplorerMetrics } from "@/lib/db/enterprise";
import ServerMonthSelector from "@/components/ServerMonthSelector";
import ExplorerCharts from "./ExplorerCharts";

export default async function CostExplorerPage({
  searchParams
}: {
  searchParams: Promise<{ month?: string; year?: string }>;
}) {
  const params = await searchParams;
  const now = new Date();
  const selectedMonth = params.month ? parseInt(params.month) : now.getMonth() + 1;
  const selectedYear = params.year ? parseInt(params.year) : now.getFullYear();

  const clientId = 'tds-enterprise-001';
  const metrics = await getCostExplorerMetrics(clientId, selectedYear, selectedMonth);

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <header style={{ marginBottom: 32, display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: "#F1F3F6", margin: "0 0 8px 0" }}>AI Cost Explorer</h1>
          <p style={{ color: "#9CA3B4", margin: 0, fontSize: 14 }}>
            Investigue onde os custos operacionais de IA estão nascendo.
          </p>
        </div>
        <ServerMonthSelector selectedMonth={selectedMonth} selectedYear={selectedYear} />
      </header>

      <ExplorerCharts 
        costByModel={metrics.costByModel} 
        topUsers={metrics.topUsers} 
        cacheTokens={metrics.cacheTokens} 
      />
    </div>
  );
}
