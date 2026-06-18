"use client";

import { useState } from "react";
import { formatCurrency } from "@/lib/utils";
import StatCard from "@/components/StatCard";
import { Activity, TrendingUp, AlertTriangle, Shield, Gauge, Calculator } from "lucide-react";

interface ForecastDashboardProps {
  totalCost: number;
  dailyAvgCost: number;
  forecastedMonthlyCost: number;
  forecastedMargin: number;
  monthlyRevenue: number;
  budgetTarget: number;
  budgetWarning: number;
  budgetHardCap: number;
  minMargin: number;
  alertStatus: 'green' | 'yellow' | 'red';
  budgetProgress: number;
  daysPassed: number;
  daysInMonth: number;
}

export default function ForecastDashboard(props: ForecastDashboardProps) {
  const {
    totalCost, dailyAvgCost, forecastedMonthlyCost, forecastedMargin,
    monthlyRevenue, budgetHardCap, minMargin, alertStatus,
    budgetProgress, daysPassed, daysInMonth
  } = props;

  // Simulador state
  const [costAdjust, setCostAdjust] = useState(100);  // %
  const [studentAdjust, setStudentAdjust] = useState(100); // %
  const [cacheAdjust, setCacheAdjust] = useState(100); // %

  const simAdjustedCost = forecastedMonthlyCost * (costAdjust / 100) * (studentAdjust / 100) * (cacheAdjust / 100);
  const simMargin = monthlyRevenue - simAdjustedCost;
  const simMarginPct = monthlyRevenue > 0 ? (simMargin / monthlyRevenue) * 100 : 0;

  // Cores do alerta
  const alertColors: Record<string, { bg: string; text: string; label: string }> = {
    green: { bg: "rgba(52,211,153,0.15)", text: "#34D399", label: "SAUDÁVEL" },
    yellow: { bg: "rgba(251,191,36,0.15)", text: "#FBBF24", label: "ATENÇÃO" },
    red: { bg: "rgba(248,113,113,0.15)", text: "#F87171", label: "CRÍTICO" }
  };

  const alert = alertColors[alertStatus];

  // Cor da barra de progresso
  const progressColor = budgetProgress < 60 ? "#34D399" : budgetProgress < 85 ? "#FBBF24" : "#F87171";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Stat Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 20 }}>
        <StatCard
          title="Custo Acumulado"
          value={formatCurrency(totalCost)}
          icon={Activity}
          accentColor="danger"
          trend={{ value: `${daysPassed}/${daysInMonth} dias`, positive: false }}
        />
        <StatCard
          title="Custo Diário Médio"
          value={formatCurrency(dailyAvgCost)}
          icon={Gauge}
          accentColor="warning"
        />
        <StatCard
          title="Forecast Mensal"
          value={formatCurrency(forecastedMonthlyCost)}
          icon={TrendingUp}
          accentColor={alertStatus === 'green' ? "primary" : "danger"}
        />
        <StatCard
          title="Margem Projetada"
          value={formatCurrency(forecastedMargin)}
          icon={Shield}
          accentColor={forecastedMargin >= minMargin ? "success" : "danger"}
          trend={{ value: `mín: ${formatCurrency(minMargin)}`, positive: forecastedMargin >= minMargin }}
        />
      </div>

      {/* Budget Progress */}
      <div style={{ background: "#1A1D26", padding: 24, borderRadius: 12, border: "1px solid #2E3340" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: "#F1F3F6", margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
            <AlertTriangle size={18} /> Status do Budget
          </h2>
          <span style={{ background: alert.bg, color: alert.text, padding: "4px 14px", borderRadius: 16, fontSize: 13, fontWeight: 600 }}>
            {alert.label}
          </span>
        </div>

        {/* Progress Bar */}
        <div style={{ background: "#0F1117", borderRadius: 8, height: 32, position: "relative", overflow: "hidden", marginBottom: 12 }}>
          <div style={{
            width: `${Math.min(budgetProgress, 100)}%`,
            height: "100%",
            background: `linear-gradient(90deg, ${progressColor}88, ${progressColor})`,
            borderRadius: 8,
            transition: "width 600ms ease",
            display: "flex", alignItems: "center", justifyContent: "flex-end", paddingRight: 12
          }}>
            <span style={{ color: "#0F1117", fontSize: 13, fontWeight: 700 }} className="font-mono">
              {budgetProgress.toFixed(1)}%
            </span>
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#9CA3B4" }}>
          <span>Consumido: {formatCurrency(totalCost)}</span>
          <span>Limite: {budgetHardCap > 0 ? formatCurrency(budgetHardCap) : formatCurrency(monthlyRevenue)}</span>
        </div>
      </div>

      {/* Simulador */}
      <div style={{ background: "#1A1D26", padding: 24, borderRadius: 12, border: "1px solid #2E3340" }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: "#F1F3F6", margin: "0 0 20px 0", display: "flex", alignItems: "center", gap: 8 }}>
          <Calculator size={18} /> Simulador de Margem
        </h2>
        <p style={{ color: "#9CA3B4", fontSize: 13, marginBottom: 24, marginTop: 0 }}>
          Ajuste os sliders abaixo para projetar cenários hipotéticos de margem.
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 24 }}>
          {/* Slider: Custo por sessão */}
          <div>
            <label style={{ color: "#9CA3B4", fontSize: 13, display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
              <span>Custo por sessão</span>
              <span style={{ color: costAdjust > 100 ? "#F87171" : "#34D399", fontWeight: 600 }} className="font-mono">{costAdjust}%</span>
            </label>
            <input
              type="range" min={50} max={200} value={costAdjust}
              onChange={e => setCostAdjust(Number(e.target.value))}
              style={{ width: "100%", accentColor: "#6366F1" }}
            />
          </div>

          {/* Slider: Nº de alunos */}
          <div>
            <label style={{ color: "#9CA3B4", fontSize: 13, display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
              <span>Volume de alunos</span>
              <span style={{ color: studentAdjust > 100 ? "#F87171" : "#34D399", fontWeight: 600 }} className="font-mono">{studentAdjust}%</span>
            </label>
            <input
              type="range" min={50} max={200} value={studentAdjust}
              onChange={e => setStudentAdjust(Number(e.target.value))}
              style={{ width: "100%", accentColor: "#6366F1" }}
            />
          </div>

          {/* Slider: Cache hit rate */}
          <div>
            <label style={{ color: "#9CA3B4", fontSize: 13, display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
              <span>Eficiência de cache</span>
              <span style={{ color: cacheAdjust < 100 ? "#34D399" : "#F87171", fontWeight: 600 }} className="font-mono">{cacheAdjust}%</span>
            </label>
            <input
              type="range" min={50} max={150} value={cacheAdjust}
              onChange={e => setCacheAdjust(Number(e.target.value))}
              style={{ width: "100%", accentColor: "#6366F1" }}
            />
          </div>
        </div>

        {/* Resultado da Simulação */}
        <div style={{
          marginTop: 24, padding: 20, borderRadius: 10,
          background: simMargin >= minMargin ? "rgba(52,211,153,0.08)" : "rgba(248,113,113,0.08)",
          border: `1px solid ${simMargin >= minMargin ? "rgba(52,211,153,0.2)" : "rgba(248,113,113,0.2)"}`
        }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, textAlign: "center" }}>
            <div>
              <p style={{ color: "#9CA3B4", fontSize: 12, marginBottom: 4 }}>Custo Simulado</p>
              <p style={{ fontSize: 20, fontWeight: 700, color: "#F1F3F6", margin: 0 }} className="font-mono">{formatCurrency(simAdjustedCost)}</p>
            </div>
            <div>
              <p style={{ color: "#9CA3B4", fontSize: 12, marginBottom: 4 }}>Margem Simulada</p>
              <p style={{ fontSize: 20, fontWeight: 700, color: simMargin >= 0 ? "#34D399" : "#F87171", margin: 0 }} className="font-mono">{formatCurrency(simMargin)}</p>
            </div>
            <div>
              <p style={{ color: "#9CA3B4", fontSize: 12, marginBottom: 4 }}>Margem %</p>
              <p style={{ fontSize: 20, fontWeight: 700, color: simMarginPct >= 20 ? "#34D399" : simMarginPct >= 0 ? "#FBBF24" : "#F87171", margin: 0 }} className="font-mono">{simMarginPct.toFixed(1)}%</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
