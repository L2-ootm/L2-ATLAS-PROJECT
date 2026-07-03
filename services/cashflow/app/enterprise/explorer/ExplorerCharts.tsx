"use client";

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid } from "recharts";
import { formatCurrency } from "@/lib/utils";

const COLORS = ['#4F8BFF', '#4F8BFF', '#00FF94', '#FFD600', '#FF0055', '#A17BFF'];

export default function ExplorerCharts({
  costByModel,
  topUsers,
  cacheTokens
}: {
  costByModel: any[];
  topUsers: any[];
  cacheTokens: { hit: number; miss: number };
}) {
  const cacheData = [
    { name: 'Cache Hit', value: cacheTokens.hit },
    { name: 'Cache Miss', value: cacheTokens.miss }
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 24 }}>
        
        {/* Cost By Model */}
        <div style={{ background: "rgba(24,28,38,0.55)", padding: 24, borderRadius: 12, border: "1px solid var(--l2-hairline)" }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: "var(--l2-fg-1)", margin: "0 0 16px 0" }}>Custo por Modelo</h2>
          <div style={{ height: 250 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={costByModel}
                  dataKey="total_cost"
                  nameKey="model_name"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  fill="#8884d8"
                  label={(props: any) => {
                    const { name, percent } = props;
                    return `${name} ${(percent * 100).toFixed(0)}%`;
                  }}
                >
                  {costByModel.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(val: any) => formatCurrency(val as number)} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Cache Efficiency */}
        <div style={{ background: "rgba(24,28,38,0.55)", padding: 24, borderRadius: 12, border: "1px solid var(--l2-hairline)" }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: "var(--l2-fg-1)", margin: "0 0 16px 0" }}>Eficiência de Cache</h2>
          <div style={{ height: 250 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={cacheData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  fill="#8884d8"
                  label={(props: any) => {
                    const { name, percent } = props;
                    return `${name} ${(percent * 100).toFixed(0)}%`;
                  }}
                >
                  <Cell fill="#00FF94" />
                  <Cell fill="#FF0055" />
                </Pie>
                <Tooltip formatter={(val: any) => `${val.toLocaleString()} tokens`} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>

      {/* Top Users */}
      <div style={{ background: "rgba(24,28,38,0.55)", padding: 24, borderRadius: 12, border: "1px solid var(--l2-hairline)" }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: "var(--l2-fg-1)", margin: "0 0 16px 0" }}>Alunos Deficitários (Top Gastos)</h2>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--l2-hairline)", color: "var(--l2-fg-2)", textAlign: "left" }}>
                <th style={{ padding: "12px 0", fontWeight: 500 }}>Aluno (User ID)</th>
                <th style={{ padding: "12px 0", fontWeight: 500, textAlign: "right" }}>Eventos</th>
                <th style={{ padding: "12px 0", fontWeight: 500, textAlign: "right" }}>Tokens Trafegados</th>
                <th style={{ padding: "12px 0", fontWeight: 500, textAlign: "right" }}>Custo Total</th>
              </tr>
            </thead>
            <tbody>
              {topUsers.map((user) => (
                <tr key={user.user_id} style={{ borderBottom: "1px solid var(--l2-hairline)" }}>
                  <td style={{ padding: "12px 0", color: "var(--l2-fg-1)", fontWeight: 500 }}>{user.user_id}</td>
                  <td style={{ padding: "12px 0", color: "var(--l2-fg-2)", textAlign: "right" }}>{user.total_events}</td>
                  <td style={{ padding: "12px 0", color: "var(--l2-fg-2)", textAlign: "right" }} className="font-mono">{(user.total_tokens || 0).toLocaleString()}</td>
                  <td style={{ padding: "12px 0", color: "#FF0055", textAlign: "right", fontWeight: 600 }} className="font-mono">{formatCurrency(user.total_cost)}</td>
                </tr>
              ))}
              {topUsers.length === 0 && (
                <tr>
                  <td colSpan={4} style={{ padding: "24px 0", textAlign: "center", color: "var(--l2-fg-2)" }}>Nenhum uso registrado neste mês.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
