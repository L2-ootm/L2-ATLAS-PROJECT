"use client";

import { useState, useEffect } from "react";
import { getClients, getInvoices } from "@/app/actions";
import { Client, Invoice } from "@/lib/types";
import { Cpu, TrendingUp, Activity, Bot } from "lucide-react";

interface AITokenLog {
    id: string;
    clientId: string;
    sourceApp: string;
    tokensPrompt: number;
    tokensCompletion: number;
    model: string;
    costUsd: number;
    timestamp: string;
}

export default function TokenTracking() {
    const [logs, setLogs] = useState<AITokenLog[]>([]);
    const [clients, setClients] = useState<Record<string, Client>>({});
    const [invoices, setInvoices] = useState<Invoice[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [clientsData, allInvoices] = await Promise.all([getClients(), getInvoices()]);
                const clientsMap = clientsData.reduce((acc: any, c: any) => ({ ...acc, [c.id]: c }), {});
                setClients(clientsMap);
                setInvoices(allInvoices);

                const res = await fetch("/api/tokens");
                if (res.ok) {
                    const data = await res.json();
                    setLogs(data.logs || []);
                }
            } catch (error) {
                console.error("Failed to fetch token logs:", error);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    const getClientRevenue = (clientId: string) => {
        return invoices
            .filter(i => i.clientId === clientId && i.status === "pago")
            .reduce((sum, i) => sum + i.amount, 0);
    };

    const metricsByClient = Object.keys(clients).map(clientId => {
        const clientLogs = logs.filter(log => log.clientId === clientId);
        const totalTokensCostUsd = clientLogs.reduce((sum, log) => sum + log.costUsd, 0);
        const totalCostBrl = totalTokensCostUsd * 5;
        const revenue = getClientRevenue(clientId);
        const marginBrl = revenue - totalCostBrl;
        const marginPercent = revenue > 0 ? (marginBrl / revenue) * 100 : 0;

        return {
            clientId,
            name: clients[clientId].name,
            totalLogs: clientLogs.length,
            totalCostBrl,
            revenue,
            marginBrl,
            marginPercent
        };
    }).filter(m => m.totalLogs > 0 || m.revenue > 0);

    if (loading) return <div className="p-6" style={{ color: "oklch(0.72 0.02 200)" }}>Carregando métricas de IA...</div>;

    return (
        <div className="topo-surface topo-shelf p-6 relative overflow-hidden">

            <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-8 gap-4">
                <div>
                    <h3 className="text-xl font-bold flex items-center gap-2" style={{
                        color: "oklch(0.95 0.01 200)",
                        fontFamily: "var(--font-sans)",
                    }}>
                        <Cpu className="w-5 h-5" style={{ color: "var(--sig-violet-edge)" }} />
                        Monitoramento de IA
                    </h3>
                    <p className="text-sm mt-1" style={{ color: "oklch(0.72 0.02 200)" }}>Monitoramento de tokens e impacto na margem de lucro</p>
                </div>
                <div className="flex items-center gap-3">
                    <span className="topo-chip topo-chip--emerald">
                        <span className="w-2 h-2 rounded-full" style={{
                            background: "var(--emerald-core)",
                            boxShadow: "0 0 6px var(--emerald-glow)",
                        }} />
                        Uso Interno L2
                    </span>
                </div>
            </div>

            {metricsByClient.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 px-4 text-center rounded-sm" style={{
                    border: "1px dashed oklch(1 0 0 / 8%)",
                    background: "oklch(0.08 0.01 220 / 40%)",
                }}>
                    <div className="w-16 h-16 rounded-full flex items-center justify-center mb-4" style={{
                        background: "oklch(0.11 0.02 220 / 60%)",
                        border: "1px solid oklch(1 0 0 / 8%)",
                    }}>
                        <Bot className="w-7 h-7" style={{ color: "oklch(0.50 0.02 200)" }} />
                    </div>
                    <h4 className="text-lg font-medium mb-2" style={{ color: "oklch(0.95 0.01 200)" }}>Nenhuma atividade de IA detectada</h4>
                    <p className="text-sm max-w-sm mb-6" style={{ color: "oklch(0.72 0.02 200)" }}>
                        Os agentes (Hunter/Sentinel) ainda não enviaram telemetria de tokens para o dashboard hoje.
                    </p>
                    <div className="inline-flex items-center gap-2 text-xs px-4 py-2 rounded-sm" style={{
                        background: "oklch(0.11 0.02 220 / 60%)",
                        border: "1px solid oklch(1 0 0 / 8%)",
                        color: "oklch(0.50 0.02 200)",
                    }}>
                        <code style={{ color: "var(--sig-violet-edge)" }}>POST /api/webhooks/tokens</code>
                    </div>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                    {metricsByClient.map((metric) => (
                        <div key={metric.clientId} className="stat-card p-6"
                            onMouseEnter={(e) => {
                                e.currentTarget.style.borderColor = "oklch(1 0 0 / 18%)";
                            }}
                            onMouseLeave={(e) => {
                                e.currentTarget.style.borderColor = "";
                            }}>

                            <div className="flex justify-between items-start mb-5">
                                <div className="flex items-center gap-3">
                                    <div className="p-3 rounded-sm" style={{
                                        background: "oklch(0.11 0.02 220 / 60%)",
                                        border: "1px solid oklch(1 0 0 / 8%)",
                                    }}>
                                        <Bot className="w-5 h-5" style={{ color: "var(--sig-violet-edge)" }} />
                                    </div>
                                    <div>
                                        <h4 className="font-bold text-base tracking-wide" style={{ color: "oklch(0.95 0.01 200)" }}>{metric.name}</h4>
                                        <span className="text-xs flex items-center gap-1.5 mt-1" style={{ color: "oklch(0.72 0.02 200)" }}>
                                            <Activity className="w-3.5 h-3.5" style={{ color: "var(--emerald-core)" }} />
                                            {metric.totalLogs} req. processadas
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <div className="flex items-center justify-between p-3 rounded-sm mb-4" style={{
                                background: "oklch(0.11 0.02 220 / 60%)",
                                border: "1px solid oklch(1 0 0 / 8%)",
                            }}>
                                <span className="text-xs font-medium uppercase tracking-wider" style={{ color: "oklch(0.72 0.02 200)" }}>Faturado Pago</span>
                                <span className="font-mono font-bold" style={{ color: "var(--emerald-core)" }}>R$ {metric.revenue.toFixed(2)}</span>
                            </div>

                            <div className="grid grid-cols-2 gap-4 mt-2 pt-4" style={{ borderTop: "1px solid oklch(1 0 0 / 5%)" }}>
                                <div>
                                    <div className="text-[11px] uppercase tracking-wider mb-1.5 flex items-center gap-1.5" style={{
                                        color: "oklch(0.72 0.02 200)",
                                        fontFamily: "var(--font-mono)",
                                    }}>
                                        <Cpu className="w-3.5 h-3.5" /> Custo LLM
                                    </div>
                                    <div className="font-mono font-medium text-lg" style={{ color: "var(--sig-crimson)" }}>
                                        <span className="text-xs mr-1 opacity-70">R$</span>
                                        {metric.totalCostBrl.toFixed(2)}
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="text-[11px] uppercase tracking-wider mb-1.5 flex items-center justify-end gap-1.5" style={{
                                        color: "oklch(0.72 0.02 200)",
                                        fontFamily: "var(--font-mono)",
                                    }}>
                                        <TrendingUp className="w-3.5 h-3.5" /> Margem
                                    </div>
                                    <div className="font-mono font-bold text-lg" style={{ color: metric.marginBrl >= 0 ? 'var(--sig-violet-edge)' : 'var(--sig-crimson)' }}>
                                        <span className="text-xs mr-1 opacity-70">R$</span>
                                        {metric.marginBrl.toFixed(2)}
                                    </div>
                                    <div className="text-[11px] mt-1 font-medium px-2 py-0.5 rounded-sm inline-block"
                                        style={{
                                            background: metric.marginPercent >= 50
                                                ? 'oklch(0.85 0.28 145 / 10%)'
                                                : metric.marginPercent > 0
                                                    ? 'oklch(0.78 0.16 85 / 10%)'
                                                    : 'oklch(0.58 0.22 20 / 10%)',
                                            color: metric.marginPercent >= 50
                                                ? 'var(--emerald-core)'
                                                : metric.marginPercent > 0
                                                    ? 'var(--sig-amber)'
                                                    : 'var(--sig-crimson)',
                                        }}>
                                        {metric.marginPercent.toFixed(1)}% Segura
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            <div className="mt-8 text-xs text-center pt-4" style={{
                borderTop: "1px solid oklch(1 0 0 / 5%)",
                color: "oklch(0.50 0.02 200)",
                fontFamily: "var(--font-mono)",
                letterSpacing: "0.05em",
            }}>
                Custo de inferência convertido em BRL ($1 = R$5,00) • Webhooks escutando em <span style={{ color: "var(--sig-violet-edge)" }}>/api/webhooks/tokens</span>
            </div>
        </div>
    );
}
