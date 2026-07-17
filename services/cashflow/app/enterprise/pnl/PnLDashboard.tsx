"use client";

import StatCard from "@/components/StatCard";
import { DollarSign, BarChart3, Target, Activity, AlertTriangle, Cpu } from "lucide-react";
import { formatCurrency } from "@/lib/utils";

interface PnLDashboardProps {
  client: { name: string; segment: string };
  contract: { name: string; min_margin_brl: number } | null;
  metrics: {
    contracted_revenue: number;
    ai_cost: number;
    margin: number;
    margin_percentage: number;
    total_input_tokens: number;
    total_output_tokens: number;
  };
  aiCostForecast: number;
  minMarginTarget: number;
  marginIsHealthy: boolean;
}

export default function PnLDashboard({
  contract,
  metrics,
  aiCostForecast,
  minMarginTarget,
  marginIsHealthy,
}: PnLDashboardProps) {
  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 20, marginBottom: 32 }}>
        <StatCard
          title="Receita Contratada"
          value={formatCurrency(metrics.contracted_revenue)}
          icon={DollarSign}
          accentColor="success"
        />
        <StatCard
          title="Custo IA (Realizado)"
          value={formatCurrency(metrics.ai_cost)}
          icon={Cpu}
          accentColor="danger"
          trend={{ value: `${metrics.total_input_tokens + metrics.total_output_tokens} tokens`, positive: false }}
        />
        <StatCard
          title="Margem Livre"
          value={formatCurrency(metrics.margin)}
          icon={BarChart3}
          accentColor={marginIsHealthy ? "primary" : "warning"}
          trend={{ value: `${metrics.margin_percentage.toFixed(1)}%`, positive: marginIsHealthy }}
        />
        <StatCard
          title="Forecast Custo IA"
          value={formatCurrency(aiCostForecast)}
          icon={Activity}
          accentColor="warning"
        />
      </div>

      <div style={{ background: "rgba(24,28,38,0.55)", padding: 24, borderRadius: 12, border: "1px solid var(--l2-hairline)", marginBottom: 24 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: "var(--l2-fg-1)", margin: "0 0 16px 0", display: "flex", alignItems: "center", gap: 8 }}>
          <Target size={18} /> Budget &amp; Alertas
        </h2>
        <div style={{ display: "flex", gap: 24, alignItems: "center" }}>
          <div style={{ flex: 1 }}>
            <p style={{ color: "var(--l2-fg-2)", fontSize: 13, marginBottom: 4 }}>Margem Mínima Alvo</p>
            <p style={{ fontSize: 20, fontWeight: 600, color: "var(--l2-fg-1)", margin: 0 }} className="font-mono">{formatCurrency(minMarginTarget)}</p>
          </div>
          <div style={{ flex: 1 }}>
            <p style={{ color: "var(--l2-fg-2)", fontSize: 13, marginBottom: 4 }}>Status</p>
            {marginIsHealthy ? (
              <span style={{ background: "rgba(52,211,153,0.15)", color: "var(--atlas-cyan)", padding: "4px 12px", borderRadius: 16, fontSize: 13, fontWeight: 600 }}>SAUDÁVEL</span>
            ) : (
              <span style={{ background: "rgba(248,113,113,0.15)", color: "var(--sig-crimson)", padding: "4px 12px", borderRadius: 16, fontSize: 13, fontWeight: 600, display: "flex", alignItems: "center", gap: 6, width: "fit-content" }}>
                <AlertTriangle size={14} /> ATENÇÃO
              </span>
            )}
          </div>
        </div>
      </div>

      <div style={{ background: "rgba(24,28,38,0.55)", padding: 24, borderRadius: 12, border: "1px solid var(--l2-hairline)" }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: "var(--l2-fg-1)", margin: "0 0 16px 0" }}>Resumo Operacional</h2>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
          <tbody>
            <tr style={{ borderBottom: "1px solid var(--l2-hairline)" }}>
              <td style={{ padding: "12px 0", color: "var(--l2-fg-2)" }}>Contrato Ativo</td>
              <td style={{ padding: "12px 0", color: "var(--l2-fg-1)", textAlign: "right", fontWeight: 500 }}>{contract?.name || "N/A"}</td>
            </tr>
            <tr style={{ borderBottom: "1px solid var(--l2-hairline)" }}>
              <td style={{ padding: "12px 0", color: "var(--l2-fg-2)" }}>Input Tokens Totais</td>
              <td style={{ padding: "12px 0", color: "var(--l2-fg-1)", textAlign: "right", fontWeight: 500 }} className="font-mono">{metrics.total_input_tokens.toLocaleString()}</td>
            </tr>
            <tr>
              <td style={{ padding: "12px 0", color: "var(--l2-fg-2)" }}>Output Tokens Totais</td>
              <td style={{ padding: "12px 0", color: "var(--l2-fg-1)", textAlign: "right", fontWeight: 500 }} className="font-mono">{metrics.total_output_tokens.toLocaleString()}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </>
  );
}
