"use client";

import { useState, useEffect, useMemo } from "react";
import { TrendingUp, DollarSign, Target, AlertTriangle, Wallet } from "lucide-react";
import StatCard from "@/components/StatCard";
import MonthSelector from "@/components/MonthSelector";
import { getClients, getExpenses } from "@/app/actions";
import { formatCurrency, getMonthYear } from "@/lib/utils";
import { Client, Expense } from "@/lib/types";
import { generateCashFlowProjection, ForecastSummary } from "@/lib/forecast";
import { calculateMEITax, TaxEstimate } from "@/lib/tax";

export default function FluxoCaixaPage() {
    const [clients, setClients] = useState<Client[]>([]);
    const [expenses, setExpenses] = useState<Expense[]>([]);
    const [month, setMonth] = useState(() => getMonthYear(new Date()));

    useEffect(() => {
        Promise.all([getClients(), getExpenses()]).then(([cls, exp]) => {
            setClients(cls);
            setExpenses(exp);
        });
    }, []);

    const activeClients = useMemo(() => clients.filter((c) => c.active), [clients]);
    const monthlyRevenue = useMemo(() => activeClients.reduce((s, c) => s + c.monthlyPayment, 0), [activeClients]);

    const forecast: ForecastSummary = useMemo(
        () => generateCashFlowProjection(activeClients, expenses, month, 6),
        [activeClients, expenses, month]
    );

    const currentMonthNum = parseInt(month.split("-")[1]);
    const taxEstimate: TaxEstimate = useMemo(
        () => calculateMEITax(monthlyRevenue, currentMonthNum),
        [monthlyRevenue, currentMonthNum]
    );

    const maxBar = useMemo(() => {
        const vals = forecast.projections.map((p) => Math.max(p.revenue, p.recurringExpenses));
        return Math.max(...vals, 1);
    }, [forecast]);

    const maxBalance = useMemo(() => {
        const vals = forecast.projections.map((p) => Math.abs(p.cumulativeBalance));
        return Math.max(...vals, 1);
    }, [forecast]);

    const alertColor = taxEstimate.alert === "danger" ? "var(--sig-crimson)" : taxEstimate.alert === "warning" ? "var(--sig-amber)" : "var(--atlas-cyan)";

    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
                <div>
                    <h1 className="text-2xl font-bold" style={{ color: "var(--l2-fg-1)" }}>Fluxo de Caixa</h1>
                    <p className="text-sm mt-0.5" style={{ color: "var(--l2-fg-3)" }}>Projeção financeira dos próximos 6 meses</p>
                </div>
                <MonthSelector value={month} onChange={setMonth} />
            </div>

            {/* Stat Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard title="Receita Mensal" value={formatCurrency(monthlyRevenue)} icon={DollarSign} accentColor="cyan" />
                <StatCard title="Lucro Projetado (3m)" value={formatCurrency(forecast.total3Months)} icon={TrendingUp} accentColor="violet" />
                <StatCard title="Lucro Projetado (6m)" value={formatCurrency(forecast.total6Months)} icon={Target} accentColor="cyan" />
                <StatCard title="DAS MEI / mês" value={formatCurrency(taxEstimate.dasMonthly)} icon={Wallet} accentColor="yellow" />
            </div>

            {/* Cash Flow Chart */}
            <div className="l2-border" style={{ borderRadius: 12, padding: 28, background: "rgba(24,28,38,0.55)" }}>
                <h2 className="text-xs font-semibold uppercase tracking-wider mb-6" style={{ color: "var(--l2-fg-2)" }}>
                    Projeção de Receita vs Despesas Recorrentes
                </h2>
                <div style={{ display: "flex", alignItems: "flex-end", gap: 16, height: 200 }}>
                    {forecast.projections.map((p) => (
                        <div key={p.month} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                            <div style={{ display: "flex", gap: 4, alignItems: "flex-end", width: "100%", height: 160 }}>
                                {/* Revenue bar */}
                                <div style={{
                                    flex: 1,
                                    height: `${(p.revenue / maxBar) * 100}%`,
                                    background: "var(--atlas-celestial)",
                                    borderRadius: "4px 4px 0 0",
                                    minHeight: 4,
                                    transition: "height 600ms cubic-bezier(0.22, 1, 0.36, 1)",
                                }} />
                                {/* Expense bar */}
                                <div style={{
                                    flex: 1,
                                    height: `${(p.recurringExpenses / maxBar) * 100}%`,
                                    background: "var(--sig-crimson)",
                                    borderRadius: "4px 4px 0 0",
                                    minHeight: 4,
                                    transition: "height 600ms cubic-bezier(0.22, 1, 0.36, 1)",
                                }} />
                            </div>
                            <span className="text-[10px] font-mono uppercase" style={{ color: "var(--l2-fg-3)" }}>{p.label}</span>
                        </div>
                    ))}
                </div>
                <div style={{ display: "flex", gap: 24, marginTop: 16 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <div style={{ width: 10, height: 10, borderRadius: 2, background: "var(--atlas-celestial)" }} />
                        <span className="text-[10px] uppercase tracking-wider" style={{ color: "var(--l2-fg-2)" }}>Receita</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <div style={{ width: 10, height: 10, borderRadius: 2, background: "var(--sig-crimson)" }} />
                        <span className="text-[10px] uppercase tracking-wider" style={{ color: "var(--l2-fg-2)" }}>Desp. Recorrentes</span>
                    </div>
                </div>
            </div>

            {/* Cumulative Balance Line */}
            <div className="l2-border" style={{ borderRadius: 12, padding: 28, background: "rgba(24,28,38,0.55)" }}>
                <h2 className="text-xs font-semibold uppercase tracking-wider mb-6" style={{ color: "var(--l2-fg-2)" }}>
                    Saldo Acumulado Projetado
                </h2>
                <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 160 }}>
                    {forecast.projections.map((p) => (
                        <div key={p.month} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                            <span className="text-[10px] font-mono" style={{ color: p.cumulativeBalance >= 0 ? "var(--atlas-cyan)" : "var(--sig-crimson)" }}>
                                {formatCurrency(p.cumulativeBalance)}
                            </span>
                            <div style={{
                                width: "100%",
                                height: `${(Math.abs(p.cumulativeBalance) / maxBalance) * 100}%`,
                                background: p.cumulativeBalance >= 0 ? "var(--atlas-cyan)" : "var(--sig-crimson)",
                                borderRadius: "4px 4px 0 0",
                                minHeight: 4,
                                transition: "height 600ms cubic-bezier(0.22, 1, 0.36, 1)",
                            }} />
                            <span className="text-[10px] font-mono uppercase" style={{ color: "var(--l2-fg-3)" }}>{p.label}</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* MEI Tax Panel & Details */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <div className="l2-border" style={{ borderRadius: 12, padding: 28, background: "rgba(24,28,38,0.55)" }}>
                    <h2 className="text-xs font-semibold uppercase tracking-wider mb-5 flex items-center gap-2" style={{ color: "var(--l2-fg-2)" }}>
                        <Wallet style={{ width: 16, height: 16, color: "var(--sig-amber)" }} /> Imposto MEI
                    </h2>
                    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <span className="text-sm" style={{ color: "var(--l2-fg-2)" }}>DAS Mensal</span>
                            <span className="text-sm font-bold font-mono" style={{ color: "var(--l2-fg-1)" }}>{formatCurrency(taxEstimate.dasMonthly)}</span>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <span className="text-sm" style={{ color: "var(--l2-fg-2)" }}>Faturamento Anual Projetado</span>
                            <span className="text-sm font-bold font-mono" style={{ color: "var(--l2-fg-1)" }}>{formatCurrency(taxEstimate.annualRevenue)}</span>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <span className="text-sm" style={{ color: "var(--l2-fg-2)" }}>Limite MEI</span>
                            <span className="text-sm font-bold font-mono" style={{ color: "var(--l2-fg-1)" }}>{formatCurrency(taxEstimate.annualLimit)}</span>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <span className="text-sm" style={{ color: "var(--l2-fg-2)" }}>Restante</span>
                            <span className="text-sm font-bold font-mono" style={{ color: alertColor }}>{formatCurrency(taxEstimate.remaining)}</span>
                        </div>
                        {/* Progress bar */}
                        <div>
                            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                                <span className="text-[10px] uppercase tracking-wider" style={{ color: "var(--l2-fg-3)" }}>Uso do Limite</span>
                                <span className="text-[10px] font-mono" style={{ color: alertColor }}>{taxEstimate.percentUsed.toFixed(1)}%</span>
                            </div>
                            <div style={{ height: 8, background: "rgba(34,40,56,0.65)", borderRadius: 4, overflow: "hidden" }}>
                                <div style={{
                                    height: "100%", width: `${taxEstimate.percentUsed}%`,
                                    background: alertColor, borderRadius: 4,
                                    transition: "width 600ms cubic-bezier(0.22, 1, 0.36, 1)",
                                }} />
                            </div>
                        </div>
                        {taxEstimate.alert !== "ok" && (
                            <div style={{
                                display: "flex", alignItems: "center", gap: 8,
                                padding: "10px 14px", borderRadius: 8,
                                background: taxEstimate.alert === "danger" ? "rgba(248,113,113,0.1)" : "rgba(251,191,36,0.1)",
                                border: `1px solid ${taxEstimate.alert === "danger" ? "rgba(248,113,113,0.2)" : "rgba(251,191,36,0.2)"}`,
                            }}>
                                <AlertTriangle style={{ width: 16, height: 16, color: alertColor, flexShrink: 0 }} />
                                <span className="text-xs" style={{ color: alertColor }}>
                                    {taxEstimate.alert === "danger"
                                        ? "Atenção! Faturamento próximo do limite MEI."
                                        : "Faturamento se aproximando do limite MEI."}
                                </span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Projection Table */}
                <div className="l2-border" style={{ borderRadius: 12, padding: 28, background: "rgba(24,28,38,0.55)" }}>
                    <h2 className="text-xs font-semibold uppercase tracking-wider mb-5 flex items-center gap-2" style={{ color: "var(--l2-fg-2)" }}>
                        <TrendingUp style={{ width: 16, height: 16, color: "var(--atlas-cyan)" }} /> Detalhes da Projeção
                    </h2>
                    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
                        {/* Header */}
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", padding: "10px 0", borderBottom: "1px solid var(--l2-hairline)" }}>
                            <span className="text-[10px] uppercase tracking-wider font-mono" style={{ color: "var(--l2-fg-3)" }}>Mês</span>
                            <span className="text-[10px] uppercase tracking-wider font-mono text-right" style={{ color: "var(--l2-fg-3)" }}>Receita</span>
                            <span className="text-[10px] uppercase tracking-wider font-mono text-right" style={{ color: "var(--l2-fg-3)" }}>Despesas</span>
                            <span className="text-[10px] uppercase tracking-wider font-mono text-right" style={{ color: "var(--l2-fg-3)" }}>Lucro</span>
                        </div>
                        {forecast.projections.map((p, i) => (
                            <div key={p.month} style={{
                                display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr",
                                padding: "12px 0", borderBottom: i < forecast.projections.length - 1 ? "1px solid rgba(34,40,56,0.65)" : "none",
                            }}>
                                <span className="text-sm font-mono" style={{ color: "var(--l2-fg-2)" }}>{p.label}</span>
                                <span className="text-sm font-mono text-right" style={{ color: "var(--l2-fg-1)" }}>{formatCurrency(p.revenue)}</span>
                                <span className="text-sm font-mono text-right" style={{ color: "var(--sig-crimson)" }}>{formatCurrency(p.recurringExpenses)}</span>
                                <span className="text-sm font-bold font-mono text-right" style={{ color: p.estimatedProfit >= 0 ? "var(--atlas-cyan)" : "var(--sig-crimson)" }}>
                                    {formatCurrency(p.estimatedProfit)}
                                </span>
                            </div>
                        ))}
                        {/* Total */}
                        <div style={{
                            display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr",
                            padding: "14px 0 0", marginTop: 4, borderTop: "1px solid var(--l2-hairline)",
                        }}>
                            <span className="text-sm font-semibold" style={{ color: "var(--l2-fg-2)" }}>Total (6m)</span>
                            <span className="text-sm font-bold font-mono text-right" style={{ color: "var(--l2-fg-1)" }}>
                                {formatCurrency(forecast.projections.reduce((s, p) => s + p.revenue, 0))}
                            </span>
                            <span className="text-sm font-bold font-mono text-right" style={{ color: "var(--sig-crimson)" }}>
                                {formatCurrency(forecast.projections.reduce((s, p) => s + p.recurringExpenses, 0))}
                            </span>
                            <span className="text-sm font-bold font-mono text-right" style={{ color: forecast.total6Months >= 0 ? "var(--atlas-cyan)" : "var(--sig-crimson)" }}>
                                {formatCurrency(forecast.total6Months)}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
