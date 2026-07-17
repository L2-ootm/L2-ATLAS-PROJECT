"use client";

import { useState } from "react";
import { formatCurrency } from "@/lib/utils";
import { FileText, Download, Printer } from "lucide-react";

interface ReportRow {
  label: string;
  value: number;
  isPercent?: boolean;
  isCount?: boolean;
}

interface ReportsDashboardProps {
  clientName: string;
  period: string;
  commercialRows: ReportRow[];
  operational: {
    summary: {
      totalSessions: number;
      totalInputTokens: number;
      totalOutputTokens: number;
      totalCost: number;
      avgCostPerSession: number;
      cacheHitRate: number;
    };
    modelBreakdown: any[];
    topUsers: any[];
  };
}

type TabType = 'commercial' | 'operational';

export default function ReportsDashboard({ clientName, period, commercialRows, operational }: ReportsDashboardProps) {
  const [activeTab, setActiveTab] = useState<TabType>('commercial');

  const exportCSV = () => {
    let csv = '';
    if (activeTab === 'commercial') {
      csv = 'Métrica,Valor\n';
      commercialRows.forEach(row => {
        const val = row.isPercent ? `${row.value.toFixed(1)}%` : row.isCount ? row.value.toString() : formatCurrency(row.value);
        csv += `"${row.label}","${val}"\n`;
      });
    } else {
      csv = 'Modelo,Sessões,Input Tokens,Output Tokens,Custo\n';
      operational.modelBreakdown.forEach((m: any) => {
        csv += `"${m.model_name}",${m.sessions},${m.input_tokens},${m.output_tokens},"${formatCurrency(m.cost)}"\n`;
      });
      csv += '\nTop Alunos\nAluno,Sessões,Tokens,Custo\n';
      operational.topUsers.forEach((u: any) => {
        csv += `"${u.user_id}",${u.sessions},${u.tokens},"${formatCurrency(u.cost)}"\n`;
      });
    }

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `relatorio-${activeTab}-${period}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const tabStyle = (tab: TabType) => ({
    padding: "10px 20px",
    borderRadius: 8,
    fontSize: 14,
    fontWeight: activeTab === tab ? 600 : 500,
    color: activeTab === tab ? "var(--atlas-celestial)" : "var(--l2-fg-2)",
    background: activeTab === tab ? "rgba(79,139,255,0.1)" : "transparent",
    border: activeTab === tab ? "1px solid rgba(79,139,255,0.18)" : "1px solid transparent",
    cursor: "pointer" as const,
    transition: "all 150ms"
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Tabs + Actions */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => setActiveTab('commercial')} style={tabStyle('commercial')}>
            <FileText size={14} style={{ display: "inline", marginRight: 6, verticalAlign: "middle" }} />
            Comercial
          </button>
          <button onClick={() => setActiveTab('operational')} style={tabStyle('operational')}>
            <FileText size={14} style={{ display: "inline", marginRight: 6, verticalAlign: "middle" }} />
            Operacional
          </button>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={exportCSV} style={{
            padding: "8px 16px", borderRadius: 8, fontSize: 13, fontWeight: 600,
            color: "var(--atlas-celestial-soft)", background: "rgba(79,139,255,0.14)", border: "1px solid rgba(79,139,255,0.38)", cursor: "pointer",
            display: "flex", alignItems: "center", gap: 6
          }}>
            <Download size={14} /> Exportar CSV
          </button>
          <button onClick={() => window.print()} style={{
            padding: "8px 16px", borderRadius: 8, fontSize: 13, fontWeight: 600,
            color: "var(--l2-fg-2)", background: "rgba(24,28,38,0.55)", border: "1px solid var(--l2-hairline)", cursor: "pointer",
            display: "flex", alignItems: "center", gap: 6
          }}>
            <Printer size={14} /> PDF
          </button>
        </div>
      </div>

      {/* Report Header (for print) */}
      <div className="print-header" style={{ display: "none" }}>
        <h1>Relatório {activeTab === 'commercial' ? 'Comercial' : 'Operacional'} — {clientName}</h1>
        <p>Período: {period}</p>
      </div>

      {/* Commercial Report */}
      {activeTab === 'commercial' && (
        <div className="print-content" style={{ background: "rgba(24,28,38,0.55)", padding: 24, borderRadius: 12, border: "1px solid var(--l2-hairline)" }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: "var(--l2-fg-1)", margin: "0 0 20px 0" }}>
            Relatório Comercial — {clientName} ({period})
          </h2>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: "2px solid var(--l2-hairline)" }}>
                <th style={{ padding: "12px 0", color: "var(--l2-fg-2)", textAlign: "left", fontWeight: 500 }}>Métrica</th>
                <th style={{ padding: "12px 0", color: "var(--l2-fg-2)", textAlign: "right", fontWeight: 500 }}>Valor</th>
              </tr>
            </thead>
            <tbody>
              {commercialRows.map((row, i) => (
                <tr key={i} style={{ borderBottom: "1px solid var(--l2-hairline)" }}>
                  <td style={{ padding: "14px 0", color: "var(--l2-fg-1)", fontWeight: row.label.includes('Margem') || row.label.includes('Receita Total') ? 600 : 400 }}>
                    {row.label}
                  </td>
                  <td style={{
                    padding: "14px 0", textAlign: "right", fontWeight: 600,
                    color: row.label.includes('Custo') ? "var(--sig-crimson)" : row.label.includes('Margem') && row.value < 0 ? "var(--sig-crimson)" : "var(--atlas-cyan)"
                  }} className="font-mono">
                    {row.isPercent ? `${row.value.toFixed(1)}%` : row.isCount ? row.value.toLocaleString() : formatCurrency(row.value)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Operational Report */}
      {activeTab === 'operational' && (
        <div className="print-content" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          {/* Summary Cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 16 }}>
            {[
              { label: "Total Sessões", value: operational.summary.totalSessions.toLocaleString() },
              { label: "Input Tokens", value: operational.summary.totalInputTokens.toLocaleString() },
              { label: "Output Tokens", value: operational.summary.totalOutputTokens.toLocaleString() },
              { label: "Custo Total", value: formatCurrency(operational.summary.totalCost) },
              { label: "Custo/Sessão", value: formatCurrency(operational.summary.avgCostPerSession) },
              { label: "Cache Hit Rate", value: `${operational.summary.cacheHitRate.toFixed(1)}%` },
            ].map((card, i) => (
              <div key={i} style={{ background: "rgba(24,28,38,0.55)", padding: 16, borderRadius: 10, border: "1px solid var(--l2-hairline)" }}>
                <p style={{ color: "var(--l2-fg-2)", fontSize: 12, marginBottom: 4, textTransform: "uppercase" }}>{card.label}</p>
                <p style={{ color: "var(--l2-fg-1)", fontSize: 20, fontWeight: 700, margin: 0 }} className="font-mono">{card.value}</p>
              </div>
            ))}
          </div>

          {/* Model Breakdown */}
          <div style={{ background: "rgba(24,28,38,0.55)", padding: 24, borderRadius: 12, border: "1px solid var(--l2-hairline)" }}>
            <h2 style={{ fontSize: 16, fontWeight: 600, color: "var(--l2-fg-1)", margin: "0 0 16px 0" }}>Breakdown por Modelo</h2>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--l2-hairline)", color: "var(--l2-fg-2)", textAlign: "left" }}>
                  <th style={{ padding: "12px 0", fontWeight: 500 }}>Modelo</th>
                  <th style={{ padding: "12px 0", fontWeight: 500, textAlign: "right" }}>Sessões</th>
                  <th style={{ padding: "12px 0", fontWeight: 500, textAlign: "right" }}>Input Tokens</th>
                  <th style={{ padding: "12px 0", fontWeight: 500, textAlign: "right" }}>Output Tokens</th>
                  <th style={{ padding: "12px 0", fontWeight: 500, textAlign: "right" }}>Custo</th>
                </tr>
              </thead>
              <tbody>
                {operational.modelBreakdown.map((m: any, i: number) => (
                  <tr key={i} style={{ borderBottom: "1px solid var(--l2-hairline)" }}>
                    <td style={{ padding: "12px 0", color: "var(--l2-fg-1)", fontWeight: 500 }}>{m.model_name}</td>
                    <td style={{ padding: "12px 0", color: "var(--l2-fg-2)", textAlign: "right" }} className="font-mono">{m.sessions}</td>
                    <td style={{ padding: "12px 0", color: "var(--l2-fg-2)", textAlign: "right" }} className="font-mono">{(m.input_tokens || 0).toLocaleString()}</td>
                    <td style={{ padding: "12px 0", color: "var(--l2-fg-2)", textAlign: "right" }} className="font-mono">{(m.output_tokens || 0).toLocaleString()}</td>
                    <td style={{ padding: "12px 0", color: "var(--sig-crimson)", textAlign: "right", fontWeight: 600 }} className="font-mono">{formatCurrency(m.cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Top Users */}
          <div style={{ background: "rgba(24,28,38,0.55)", padding: 24, borderRadius: 12, border: "1px solid var(--l2-hairline)" }}>
            <h2 style={{ fontSize: 16, fontWeight: 600, color: "var(--l2-fg-1)", margin: "0 0 16px 0" }}>Top 10 Alunos por Custo</h2>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--l2-hairline)", color: "var(--l2-fg-2)", textAlign: "left" }}>
                  <th style={{ padding: "12px 0", fontWeight: 500 }}>Aluno</th>
                  <th style={{ padding: "12px 0", fontWeight: 500, textAlign: "right" }}>Sessões</th>
                  <th style={{ padding: "12px 0", fontWeight: 500, textAlign: "right" }}>Tokens</th>
                  <th style={{ padding: "12px 0", fontWeight: 500, textAlign: "right" }}>Custo</th>
                </tr>
              </thead>
              <tbody>
                {operational.topUsers.map((u: any, i: number) => (
                  <tr key={i} style={{ borderBottom: "1px solid var(--l2-hairline)" }}>
                    <td style={{ padding: "12px 0", color: "var(--l2-fg-1)", fontWeight: 500 }}>{u.user_id}</td>
                    <td style={{ padding: "12px 0", color: "var(--l2-fg-2)", textAlign: "right" }} className="font-mono">{u.sessions}</td>
                    <td style={{ padding: "12px 0", color: "var(--l2-fg-2)", textAlign: "right" }} className="font-mono">{(u.tokens || 0).toLocaleString()}</td>
                    <td style={{ padding: "12px 0", color: "var(--sig-crimson)", textAlign: "right", fontWeight: 600 }} className="font-mono">{formatCurrency(u.cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Print Styles */}
      <style>{`
        @media print {
          body { background: white !important; color: black !important; }
          .sidebar-wrapper, .mobile-menu-btn, header, button { display: none !important; }
          .print-header { display: block !important; }
          .print-content { background: white !important; border: 1px solid #ccc !important; }
          .print-content td, .print-content th { color: black !important; }
          .font-mono { font-family: monospace; }
        }
      `}</style>
    </div>
  );
}
