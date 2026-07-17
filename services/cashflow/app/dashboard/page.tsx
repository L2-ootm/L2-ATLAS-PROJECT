"use client";

import { useState, useEffect, useMemo } from "react";
import { DollarSign, TrendingDown, TrendingUp, Users, AlertTriangle } from "lucide-react";
import Link from "next/link";
import StatCard from "@/components/StatCard";
import MonthSelector from "@/components/MonthSelector";
import TokenTracking from "@/components/TokenTracking";
import GoalRings from "@/components/dashboard/GoalRings";
import LiveCommandFeed from "@/components/dashboard/LiveCommandFeed";
import ExpenseDonutChart from "@/components/dashboard/ExpenseDonutChart";
import TokenHeatmap from "@/components/dashboard/TokenHeatmap";
import { getClients, getExpenses, getInvoices } from "@/app/actions";
import { formatCurrency, getMonthYear } from "@/lib/utils";
import type { Client, Expense, Invoice } from "@/lib/types";

export default function DashboardPage() {
    const [month, setMonth] = useState(() => getMonthYear(new Date()));
    const [clients, setClients] = useState<Client[]>([]);
    const [expenses, setExpenses] = useState<Expense[]>([]);
    const [overdueInvoices, setOverdueInvoices] = useState<Invoice[]>([]);
    const [dueSoonInvoices, setDueSoonInvoices] = useState<Invoice[]>([]);
    const [allInvoices, setAllInvoices] = useState<Invoice[]>([]);

    useEffect(() => {
        Promise.all([getClients(), getExpenses(), getInvoices()]).then(([cls, exp, invs]) => {
            setClients(cls);
            setExpenses(exp);
            setAllInvoices(invs);

            const today = new Date();
            const todayStr = today.toISOString().split("T")[0];
            const futureDate = new Date(today.getTime() + 7 * 86400000).toISOString().split("T")[0];

            setOverdueInvoices(invs.filter((invoice) => invoice.status === "pendente" && invoice.dueDate < todayStr));
            setDueSoonInvoices(invs.filter((invoice) => invoice.status === "pendente" && invoice.dueDate >= todayStr && invoice.dueDate <= futureDate));
        });
    }, []);

    const activeClients = useMemo(() => clients.filter((c) => c.active), [clients]);
    const monthExpenses = useMemo(() => expenses.filter((e) => e.date.startsWith(month)), [expenses, month]);
    const revenue = useMemo(() => activeClients.reduce((sum, c) => sum + c.monthlyPayment, 0), [activeClients]);
    const totalExpenses = useMemo(() => monthExpenses.reduce((sum, e) => sum + e.amount, 0), [monthExpenses]);
    const profit = revenue - totalExpenses;
    const margin = revenue > 0 ? ((profit / revenue) * 100).toFixed(1) : "0";

    const expiringContracts = useMemo(() => {
        const today = new Date();
        return activeClients.filter((c) => {
            if (!c.contractMonths || c.contractMonths === 0) return false;
            const end = new Date(c.startDate);
            end.setMonth(end.getMonth() + c.contractMonths);
            const daysRemaining = Math.ceil((end.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
            return daysRemaining >= 0 && daysRemaining <= 30;
        }).map(c => {
            const end = new Date(c.startDate);
            end.setMonth(end.getMonth() + (c.contractMonths || 0));
            const daysRemaining = Math.ceil((end.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
            return { ...c, endDate: end.toISOString().split("T")[0], daysRemaining };
        });
    }, [activeClients]);

    const alertInvoices = [...overdueInvoices, ...dueSoonInvoices];

    return (
        <div className="dashboard-layout">
            {/* Main Content Area */}
            <div className="dashboard-main flex flex-col gap-5 min-w-0">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                        <h1 style={{
                            fontSize: "1.5rem", fontWeight: 700,
                            letterSpacing: "var(--tr-tight)",
                            color: "oklch(0.95 0.01 200)",
                            fontFamily: "var(--font-sans)",
                        }}>Visão Geral</h1>
                        <p style={{
                            fontSize: 14, marginTop: 2,
                            color: "oklch(0.50 0.02 200)",
                            fontFamily: "var(--font-mono)",
                            letterSpacing: "0.05em",
                        }}>Visão geral financeira da L2</p>
                    </div>
                    <MonthSelector value={month} onChange={setMonth} />
                </div>

                {/* Top Grid: Goal Rings & Stats */}
                <div className="dashboard-overview-grid">
                    <div>
                        <GoalRings revenue={revenue} expenses={totalExpenses} goal={50000} />
                    </div>
                    <div className="dashboard-stat-grid">
                        <StatCard title="Faturamento" value={formatCurrency(revenue)} icon={DollarSign} accentColor="cyan" />
                        <StatCard title="Despesas" value={formatCurrency(totalExpenses)} icon={TrendingDown} accentColor="red" />
                        <StatCard title="Lucro Líquido" value={formatCurrency(profit)} icon={TrendingUp}
                            accentColor={profit >= 0 ? "violet" : "red"} trend={{ value: `${margin}% margem`, positive: profit >= 0 }} />
                        <StatCard title="Clientes Ativos" value={String(activeClients.length)} icon={Users} accentColor="cyan" />
                    </div>
                </div>

                {/* Data Visualizations */}
                <div className="dashboard-chart-grid">
                    <div className="h-full"><ExpenseDonutChart expenses={monthExpenses} /></div>
                    <div className="h-full"><TokenHeatmap clients={activeClients} invoices={allInvoices} /></div>
                </div>

                {/* Alerts Section */}
                {(alertInvoices.length > 0 || expiringContracts.length > 0) && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-2">
                        {alertInvoices.length > 0 && (
                            <div className="stat-card p-5" style={{ borderColor: "oklch(0.58 0.22 20 / 25%)" }}>
                                <div className="flex items-center justify-between mb-4">
                                    <h2 style={{
                                        fontSize: 11, fontWeight: 600, textTransform: "uppercase" as const,
                                        letterSpacing: "0.12em", display: "flex", alignItems: "center", gap: 8,
                                        color: "oklch(0.72 0.02 200)",
                                        fontFamily: "var(--font-mono)",
                                    }}>
                                        <AlertTriangle style={{ width: 16, height: 16, color: "var(--sig-crimson)" }} /> Faturas Pendentes
                                    </h2>
                                    <Link href="/faturas" className="topo-btn topo-btn--muted" style={{
                                        fontSize: 10, padding: "3px 8px",
                                    }}>Ver todas →</Link>
                                </div>
                                <div className="space-y-2">
                                    {overdueInvoices.slice(0, 3).map((inv) => (
                                        <div key={inv.id} className="flex justify-between items-center p-3 rounded-sm"
                                            style={{
                                                background: "oklch(0.58 0.22 20 / 6%)",
                                                border: "1px solid oklch(0.58 0.22 20 / 15%)",
                                            }}>
                                            <div>
                                                <p style={{ fontSize: 12, fontWeight: 500, color: "oklch(0.95 0.01 200)", fontFamily: "var(--font-sans)" }}>{inv.clientName}</p>
                                                <p style={{ fontSize: 9, fontFamily: "var(--font-mono)", marginTop: 2, color: "var(--sig-crimson)" }}>ATRASADO</p>
                                            </div>
                                            <span style={{ fontSize: 14, fontWeight: 700, color: "oklch(0.95 0.01 200)", fontFamily: "var(--font-mono)" }}>{formatCurrency(inv.amount)}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {expiringContracts.length > 0 && (
                            <div className="stat-card p-5" style={{ borderColor: "oklch(0.78 0.16 85 / 25%)" }}>
                                <div className="flex items-center justify-between mb-4">
                                    <h2 style={{
                                        fontSize: 11, fontWeight: 600, textTransform: "uppercase" as const,
                                        letterSpacing: "0.12em", display: "flex", alignItems: "center", gap: 8,
                                        color: "oklch(0.72 0.02 200)",
                                        fontFamily: "var(--font-mono)",
                                    }}>
                                        <AlertTriangle style={{ width: 16, height: 16, color: "var(--sig-amber)" }} /> Vencimento de Contratos
                                    </h2>
                                    <Link href="/contratos" className="topo-btn topo-btn--muted" style={{
                                        fontSize: 10, padding: "3px 8px",
                                    }}>Ver todos →</Link>
                                </div>
                                <div className="space-y-2">
                                    {expiringContracts.slice(0, 3).sort((a, b) => a.daysRemaining - b.daysRemaining).map((c) => (
                                        <div key={c.id} className="flex justify-between items-center p-3 rounded-sm"
                                            style={{
                                                background: "oklch(0.78 0.16 85 / 6%)",
                                                border: "1px solid oklch(0.78 0.16 85 / 15%)",
                                            }}>
                                            <div>
                                                <p style={{ fontSize: 12, fontWeight: 500, color: "oklch(0.95 0.01 200)", fontFamily: "var(--font-sans)" }}>{c.name}</p>
                                                <p style={{ fontSize: 9, fontFamily: "var(--font-mono)", marginTop: 2, color: "var(--sig-amber)" }}>{c.daysRemaining === 0 ? 'HOJE' : `EM ${c.daysRemaining} DIAS`}</p>
                                            </div>
                                            <span style={{ fontSize: 14, fontWeight: 700, color: "oklch(0.95 0.01 200)", fontFamily: "var(--font-mono)" }}>{formatCurrency(c.monthlyPayment)}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* TokenTracking component */}
                <div className="mt-4">
                    <TokenTracking />
                </div>
            </div>

            {/* Right Sidebar: Activity Feed */}
            <aside className="dashboard-activity-rail">
                <div>
                    <LiveCommandFeed expenses={expenses} invoices={allInvoices} />
                </div>
            </aside>
        </div>
    );
}
