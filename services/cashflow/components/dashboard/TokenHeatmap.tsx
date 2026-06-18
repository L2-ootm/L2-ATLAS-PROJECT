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
                <div className="l2-border rounded-lg p-3" style={{ background: "#1A1D26", boxShadow: "0 8px 24px rgba(0,0,0,0.3)" }}>
                    <p className="text-xs font-bold mb-1" style={{ color: "#F1F3F6" }}>{data.name}</p>
                    <div className="space-y-1 mt-2">
                        <p className="text-[10px] flex justify-between gap-4" style={{ color: "#9CA3B4" }}>
                            <span>Receita:</span> <span className="font-mono">{formatCurrency(data.revenue)}</span>
                        </p>
                        <p className="text-[10px] flex justify-between gap-4" style={{ color: "#9CA3B4" }}>
                            <span>Custo IA:</span> <span className="font-mono" style={{ color: "#F87171" }}>{formatCurrency(data.cost)}</span>
                        </p>
                        <hr style={{ border: "none", borderTop: "1px solid #2E3340", margin: "4px 0" }} />
                        <p className={`text-[10px] font-bold flex justify-between gap-4`} style={{ color: isDanger ? '#F87171' : '#34D399' }}>
                            <span>Margem:</span> <span className="font-mono">{data.marginPercent.toFixed(1)}%</span>
                        </p>
                    </div>
                </div>
            );
        }
        return null;
    };

    return (
        <div className="l2-border rounded-xl p-6 h-full flex flex-col relative overflow-hidden transition-colors" style={{ background: "#1A1D26" }}>

            <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold flex items-center gap-2" style={{ color: "#F1F3F6" }}>
                    <Bot className="w-4 h-4" style={{ color: "#34D399" }} />
                    Custo IA por Cliente
                </h3>
                {loading && <span className="text-[10px]" style={{ color: "#5C6478" }}>Carregando...</span>}
            </div>

            <div className="flex-1 min-h-[200px]">
                {data.length === 0 && !loading ? (
                    <div className="absolute inset-0 flex items-center justify-center text-xs" style={{ color: "#5C6478" }}>Sem dados suficientes.</div>
                ) : (
                    <ResponsiveContainer width="100%" height="100%">
                        <ScatterChart margin={{ top: 10, right: 10, bottom: -10, left: -20 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#252937" vertical={false} />
                            <XAxis
                                type="number"
                                dataKey="revenue"
                                name="Receita"
                                tickFormatter={(val) => `R$${val / 1000}k`}
                                stroke="#2E3340"
                                tick={{ fontSize: 10, fill: '#5C6478' }}
                                axisLine={false}
                                tickLine={false}
                            />
                            <YAxis
                                type="number"
                                dataKey="cost"
                                name="Custo IA"
                                tickFormatter={(val) => `R$${val}`}
                                stroke="#2E3340"
                                tick={{ fontSize: 10, fill: '#5C6478' }}
                                axisLine={false}
                                tickLine={false}
                            />
                            <ZAxis type="number" dataKey="z" range={[60, 100]} />
                            <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3', stroke: '#3D4255' }} />
                            <Scatter
                                name="Clientes"
                                data={data}
                                shape={(props: any) => {
                                    const { cx, cy, payload } = props;
                                    const isDanger = payload.marginPercent < 60;
                                    const colorPrimary = isDanger ? '#F87171' : '#34D399';

                                    return (
                                        <g transform={`translate(${cx},${cy})`}>
                                            <circle r="6" fill={colorPrimary} opacity={0.8} />
                                        </g>
                                    );
                                }}
                            />
                        </ScatterChart>
                    </ResponsiveContainer>
                )}
            </div>
            <div className="text-[9px] text-center mt-2" style={{ color: "#5C6478" }}>
                Eixo X: Receita Total | Eixo Y: Custo de Inferência LLM (R$)
            </div>
        </div>
    );
}
