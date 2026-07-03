import { getBillingMetrics } from "@/lib/db/enterprise";
import ServerMonthSelector from "@/components/ServerMonthSelector";
import BillingDashboard from "./BillingDashboard";

export default async function BillingPlusPage({
  searchParams
}: {
  searchParams: Promise<{ month?: string; year?: string }>;
}) {
  const params = await searchParams;
  const now = new Date();
  const selectedMonth = params.month ? parseInt(params.month) : now.getMonth() + 1;
  const selectedYear = params.year ? parseInt(params.year) : now.getFullYear();

  const clientId = 'tds-enterprise-001';
  const metrics = await getBillingMetrics(clientId, selectedYear, selectedMonth);

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <header style={{ marginBottom: 32, display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--l2-fg-1)", margin: "0 0 8px 0" }}>Billing Plus</h1>
          <p style={{ color: "var(--l2-fg-2)", margin: 0, fontSize: 14 }}>
            Gestão de assinaturas LeticIA Plus e reconciliação de pagamentos.
          </p>
        </div>
        <ServerMonthSelector selectedMonth={selectedMonth} selectedYear={selectedYear} />
      </header>

      <BillingDashboard
        totals={metrics.totals}
        activeSubscriptions={metrics.activeSubscriptions}
        recentEvents={metrics.recentEvents}
      />
    </div>
  );
}
