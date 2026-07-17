import { getForecastData } from "@/lib/db/enterprise";
import ServerMonthSelector from "@/components/ServerMonthSelector";
import ForecastDashboard from "./ForecastDashboard";

export default async function ForecastPage({
  searchParams
}: {
  searchParams: Promise<{ month?: string; year?: string }>;
}) {
  const params = await searchParams;
  const now = new Date();
  const selectedMonth = params.month ? parseInt(params.month) : now.getMonth() + 1;
  const selectedYear = params.year ? parseInt(params.year) : now.getFullYear();

  const clientId = 'tds-enterprise-001';
  const forecast = await getForecastData(clientId, selectedYear, selectedMonth);

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <header style={{ marginBottom: 32, display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--l2-fg-1)", margin: "0 0 8px 0" }}>Forecast &amp; Alertas</h1>
          <p style={{ color: "var(--l2-fg-2)", margin: 0, fontSize: 14 }}>
            Projeção de custos, alertas de budget e simulador de margem.
          </p>
        </div>
        <ServerMonthSelector selectedMonth={selectedMonth} selectedYear={selectedYear} />
      </header>

      <ForecastDashboard
        totalCost={forecast.totalCost}
        dailyAvgCost={forecast.dailyAvgCost}
        forecastedMonthlyCost={forecast.forecastedMonthlyCost}
        forecastedMargin={forecast.forecastedMargin}
        monthlyRevenue={forecast.monthlyRevenue}
        budgetTarget={forecast.budgetTarget}
        budgetWarning={forecast.budgetWarning}
        budgetHardCap={forecast.budgetHardCap}
        minMargin={forecast.minMargin}
        alertStatus={forecast.alertStatus}
        budgetProgress={forecast.budgetProgress}
        daysPassed={forecast.daysPassed}
        daysInMonth={forecast.daysInMonth}
      />
    </div>
  );
}
