"use client";

import { useEffect, useState, useMemo } from "react";
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ZAxis } from "recharts";
import { Client, Invoice } from "@/lib/types";
import { formatCurrency } from "@/lib/utils";
import { Bot } from "lucide-react";

interface AITokenLog {
    clientId: string;
    costUsd: number;
}

interface TokenHeatmapProps {
    clients: Client[];
    invoices: Invoice[];
}

export default function TokenHeatmap({ clients, invoices }: TokenHeatmapProps) {
    const [logs, setLogs] = useState<AITokenLog[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchTokens = async () => {
            try {
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
        fetchTokens();
    }, []);

    const data = useMemo(() => {
        if (!clients.length) return [];

        return clients.map(client => {
            const clientLogs = logs.filter(log => log.clientId === client.id);
            const totalTokensCostUsd = clientLogs.reduce((sum, log) => sum + log.costUsd, 0);
            const totalCostBrl = totalTokensCostUsd * 5;

            const revenue = invoices
                .filter(i => i.clientId === client.id && i.status === "pago")
                .reduce((sum, i) => sum + i.amount, 0);

            const marginBrl = revenue - totalCostBrl;
            const marginPercent = revenue > 0 ? (marginBrl / revenue) * 100 : 0;

            return {
                id: client.id,
                name: client.name,
                revenue,
                cost: totalCostBrl,
                marginPercent,
                z: 1,
            };
        }).filter(item => item.revenue > 0 || item.cost > 0);
    }, [clients, invoices, logs]);

    const CustomTooltip = ({ active, payload }: any) => {
        if (active && payload && payload.length) {
            const data = payload[0].payload;
            const isDanger = data.marginPercent < 50;
            return (
                <div className="topo-surface p-3" style={{ boxShadow: "0 8px 24px rgba(0,0,0,0.4)" }}>
                    <p className="text-xs font-bold mb-1" style={{ color: "oklch(0.95 0.01 200)" }}>{data.name}</p>
                    <div className="space-y-1 mt-2">
                        <p className="text-[10px] flex justify-between gap-4" style={{ color: "oklch(0.72 0.02 200)" }}>
                            <span>Receita:</span> <span className="font-mono">{formatCurrency(data.revenue)}</span>
                        </p>
                        <p className="text-[10px] flex justify-between gap-4" style={{ color: "oklch(0.72 0.02 200)" }}>
                            <span>Custo IA:</span> <span className="font-mono" style={{ color: "var(--sig-crimson)" }}>{formatCurrency(data.cost)}</span>
                        </p>
                        <hr style={{ border: "none", borderTop: "1px solid oklch(1 0 0 / 5%)", margin: "4px 0" }} />
                        <p className="text-[10px] font-bold flex justify-between gap-4" style={{ color: isDanger ? 'var(--sig-crimson)' : 'var(--emerald-core)' }}>
                            <span>Margem:</span> <span className="font-mono">{data.marginPercent.toFixed(1)}%</span>
                        </p>
                    </div>
                </div>
            );
        }
        return null;
    };

    return (
        <div className="topo-surface topo-shelf p-6 h-full flex flex-col relative overflow-hidden">

            <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold flex items-center gap-2" style={{
                    color: "oklch(0.95 0.01 200)",
                    fontFamily: "var(--font-mono)",
                    letterSpacing: "0.08em",
                }}>
                    <Bot className="w-4 h-4" style={{ color: "var(--emerald-core)" }} />
                    Custo IA por Cliente
                </h3>
                {loading && <span className="text-[10px]" style={{ color: "oklch(0.50 0.02 200)" }}>Carregando...</span>}
            </div>

            <div className="flex-1 min-h-[200px]">
                {data.length === 0 && !loading ? (
                    <div className="absolute inset-0 flex items-center justify-center text-xs" style={{ color: "oklch(0.50 0.02 200)" }}>Sem dados suficientes.</div>
                ) : (
                    <ResponsiveContainer width="100%" height="100%">
                        <ScatterChart margin={{ top: 10, right: 10, bottom: -10, left: -20 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="oklch(1 0 0 / 5%)" vertical={false} />
                            <XAxis
                                type="number"
                                dataKey="revenue"
                                name="Receita"
                                tickFormatter={(val) => `R$${val / 1000}k`}
                                stroke="oklch(1 0 0 / 5%)"
                                tick={{ fontSize: 10, fill: 'oklch(0.50 0.02 200)' }}
                                axisLine={false}
                                tickLine={false}
                            />
                            <YAxis
                                type="number"
                                dataKey="cost"
                                name="Custo IA"
                                tickFormatter={(val) => `R$${val}`}
                                stroke="oklch(1 0 0 / 5%)"
                                tick={{ fontSize: 10, fill: 'oklch(0.50 0.02 200)' }}
                                axisLine={false}
                                tickLine={false}
                            />
                            <ZAxis type="number" dataKey="z" range={[60, 100]} />
                            <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3', stroke: 'oklch(1 0 0 / 8%)' }} />
                            <Scatter
                                name="Clientes"
                                data={data}
                                shape={(props: any) => {
                                    const { cx, cy, payload } = props;
                                    const isDanger = payload.marginPercent < 60;
                                    const colorPrimary = isDanger ? 'var(--sig-crimson)' : 'var(--emerald-core)';

                                    return (
                                        <g transform={`translate(${cx},${cy})`}>
                                            <circle r="6" fill={colorPrimary} opacity={0.8} style={{
                                                filter: `drop-shadow(0 0 4px ${isDanger ? 'rgba(255,0,85,0.3)' : 'rgba(70,240,224,0.3)'})`,
                                            }} />
                                        </g>
                                    );
                                }}
                            />
                        </ScatterChart>
                    </ResponsiveContainer>
                )}
            </div>
            <div className="text-[9px] text-center mt-2" style={{
                color: "oklch(0.50 0.02 200)",
                fontFamily: "var(--font-mono)",
                letterSpacing: "0.08em",
            }}>
                Eixo X: Receita Total | Eixo Y: Custo de Inferência LLM (R$)
            </div>
        </div>
    );
}
