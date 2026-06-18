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
                // Fetch internal clients and invoices from SQLite backend
                const [clientsData, allInvoices] = await Promise.all([getClients(), getInvoices()]);
                const clientsMap = clientsData.reduce((acc: any, c: any) => ({ ...acc, [c.id]: c }), {});
                setClients(clientsMap);
                setInvoices(allInvoices);

                // Fetch token logs from our local API
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

    // Helper to calculate total revenue from paid invoices for a client
    const getClientRevenue = (clientId: string) => {
        return invoices
            .filter(i => i.clientId === clientId && i.status === "pago")
            .reduce((sum, i) => sum + i.amount, 0);
    };

    // Calculate aggregated metrics by client
    const metricsByClient = Object.keys(clients).map(clientId => {
        const clientLogs = logs.filter(log => log.clientId === clientId);
        const totalTokensCostUsd = clientLogs.reduce((sum, log) => sum + log.costUsd, 0);
        // Assuming conversion rate 1 USD = 5 BRL for this internal test
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

    if (loading) return <div className="p-6" style={{ color: "#9CA3B4" }}>Carregando métricas de IA...</div>;

    return (
        <div className="l2-border rounded-xl p-6 relative overflow-hidden" style={{ background: "#1A1D26" }}>

            <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-8 gap-4">
                <div>
                    <h3 className="text-xl font-bold flex items-center gap-2" style={{ color: "#F1F3F6" }}>
                        <Cpu className="w-5 h-5" style={{ color: "#6366F1" }} />
                        Monitoramento de IA
                    </h3>
                    <p className="text-sm mt-1" style={{ color: "#9CA3B4" }}>Monitoramento de tokens e impacto na margem de lucro</p>
                </div>
                <div className="flex items-center gap-3">
                    <span className="px-3 py-1.5 text-xs rounded-full flex items-center gap-2"
                        style={{ background: "#252937", color: "#9CA3B4", border: "1px solid #2E3340" }}>
                        <span className="w-2 h-2 rounded-full" style={{ background: "#34D399" }} />
                        Uso Interno L2
                    </span>
                </div>
            </div>

            {metricsByClient.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 px-4 text-center rounded-xl" style={{ border: "1px dashed #2E3340", background: "#1F2230" }}>
                    <div className="w-16 h-16 rounded-full flex items-center justify-center mb-4" style={{ background: "#252937", border: "1px solid #2E3340" }}>
                        <Bot className="w-7 h-7" style={{ color: "#5C6478" }} />
                    </div>
                    <h4 className="text-lg font-medium mb-2" style={{ color: "#F1F3F6" }}>Nenhuma atividade de IA detectada</h4>
                    <p className="text-sm max-w-sm mb-6" style={{ color: "#9CA3B4" }}>
                        Os agentes (Hunter/Sentinel) ainda não enviaram telemetria de tokens para o dashboard hoje.
                    </p>
                    <div className="inline-flex items-center gap-2 text-xs px-4 py-2 rounded-lg" style={{ background: "#252937", border: "1px solid #2E3340", color: "#5C6478" }}>
                        <code style={{ color: "#6366F1" }}>POST /api/webhooks/tokens</code>
                    </div>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                    {metricsByClient.map((metric) => (
                        <div key={metric.clientId} className="l2-border rounded-xl p-6 transition-colors"
                            style={{ background: "#1F2230" }}
                            onMouseEnter={(e) => { e.currentTarget.style.borderColor = "#3D4255"; }}
                            onMouseLeave={(e) => { e.currentTarget.style.borderColor = "#2E3340"; }}>

                            <div className="flex justify-between items-start mb-5">
                                <div className="flex items-center gap-3">
                                    <div className="p-3 rounded-xl" style={{ background: "#252937", border: "1px solid #2E3340" }}>
                                        <Bot className="w-5 h-5" style={{ color: "#6366F1" }} />
                                    </div>
                                    <div>
                                        <h4 className="font-bold text-base tracking-wide" style={{ color: "#F1F3F6" }}>{metric.name}</h4>
                                        <span className="text-xs flex items-center gap-1.5 mt-1" style={{ color: "#9CA3B4" }}>
                                            <Activity className="w-3.5 h-3.5" style={{ color: "#34D399" }} />
                                            {metric.totalLogs} req. processadas
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <div className="flex items-center justify-between p-3 rounded-lg mb-4" style={{ background: "#252937", border: "1px solid #2E3340" }}>
                                <span className="text-xs font-medium uppercase tracking-wider" style={{ color: "#9CA3B4" }}>Faturado Pago</span>
                                <span className="font-mono font-bold" style={{ color: "#34D399" }}>R$ {metric.revenue.toFixed(2)}</span>
                            </div>

                            <div className="grid grid-cols-2 gap-4 mt-2 pt-4" style={{ borderTop: "1px solid #2E3340" }}>
                                <div>
                                    <div className="text-[11px] uppercase tracking-wider mb-1.5 flex items-center gap-1.5" style={{ color: "#9CA3B4" }}>
                                        <Cpu className="w-3.5 h-3.5" /> Custo LLM
                                    </div>
                                    <div className="font-mono font-medium text-lg" style={{ color: "#F87171" }}>
                                        <span className="text-xs mr-1 opacity-70">R$</span>
                                        {metric.totalCostBrl.toFixed(2)}
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="text-[11px] uppercase tracking-wider mb-1.5 flex items-center justify-end gap-1.5" style={{ color: "#9CA3B4" }}>
                                        <TrendingUp className="w-3.5 h-3.5" /> Margem
                                    </div>
                                    <div className="font-mono font-bold text-lg" style={{ color: metric.marginBrl >= 0 ? '#6366F1' : '#F87171' }}>
                                        <span className="text-xs mr-1 opacity-70">R$</span>
                                        {metric.marginBrl.toFixed(2)}
                                    </div>
                                    <div className="text-[11px] mt-1 font-medium px-2 py-0.5 rounded inline-block"
                                        style={{
                                            background: metric.marginPercent >= 50 ? 'rgba(52,211,153,0.1)' : metric.marginPercent > 0 ? 'rgba(251,191,36,0.1)' : 'rgba(248,113,113,0.1)',
                                            color: metric.marginPercent >= 50 ? '#34D399' : metric.marginPercent > 0 ? '#FBBF24' : '#F87171',
                                        }}>
                                        {metric.marginPercent.toFixed(1)}% Segura
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            <div className="mt-8 text-xs text-center pt-4" style={{ borderTop: "1px solid #2E3340", color: "#5C6478" }}>
                Custo de inferência convertido em BRL ($1 = R$5,00) • Webhooks escutando em <span className="font-mono" style={{ color: "#6366F1" }}>/api/webhooks/tokens</span>
            </div>
        </div>
    );
}
