"use client";

import { useMemo } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { Expense, EXPENSE_CATEGORIES } from "@/lib/types";
import { formatCurrency } from "@/lib/utils";
import { PieChart as PieChartIcon } from "lucide-react";

interface ExpenseDonutChartProps {
    expenses: Expense[];
}

export default function ExpenseDonutChart({ expenses }: ExpenseDonutChartProps) {
    const data = useMemo(() => {
        const map: Record<string, number> = {};
        expenses.forEach((e) => {
            map[e.category] = (map[e.category] || 0) + e.amount;
        });

        return EXPENSE_CATEGORIES.map((cat) => ({
            name: cat,
            value: map[cat] || 0,
        })).filter(item => item.value > 0).sort((a, b) => b.value - a.value);
    }, [expenses]);

    const COLORS: Record<string, string> = {
        'Software': '#818CF8',
        'Marketing': '#FBBF24',
        'Equipamento': '#34D399',
        'Infraestrutura': '#94A3B8',
        'Pessoal': '#A78BFA',
        'Outros': '#64748B',
    };

    const CustomTooltip = ({ active, payload }: any) => {
        if (active && payload && payload.length) {
            return (
                <div className="l2-border rounded-lg p-3" style={{ background: "#1A1D26", boxShadow: "0 8px 24px rgba(0,0,0,0.3)" }}>
                    <p className="text-xs font-medium mb-1" style={{ color: "#9CA3B4" }}>{payload[0].name}</p>
                    <p className="text-sm font-bold font-mono" style={{ color: payload[0].payload.fill }}>
                        {formatCurrency(payload[0].value)}
                    </p>
                </div>
            );
        }
        return null;
    };

    return (
        <div className="l2-border rounded-xl p-6 h-full flex flex-col transition-colors" style={{ background: "#1A1D26" }}>

            <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold flex items-center gap-2" style={{ color: "#F1F3F6" }}>
                    <PieChartIcon className="w-4 h-4" style={{ color: "#6366F1" }} />
                    Distribuição de Custos
                </h3>
            </div>

            {data.length === 0 ? (
                <div className="flex-1 flex items-center justify-center text-sm" style={{ color: "#5C6478" }}>Sem despesas registradas.</div>
            ) : (
                <div className="flex-1 min-h-[220px] relative">
                    <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'transparent' }} />
                            <Pie
                                data={data}
                                cx="50%"
                                cy="50%"
                                innerRadius={60}
                                outerRadius={80}
                                paddingAngle={5}
                                dataKey="value"
                                stroke="transparent"
                            >
                                {data.map((entry, index) => (
                                    <Cell
                                        key={`cell-${index}`}
                                        fill={COLORS[entry.name] || COLORS['Outros']}
                                        className="hover:opacity-80 transition-opacity duration-300 cursor-pointer"
                                    />
                                ))}
                            </Pie>
                        </PieChart>
                    </ResponsiveContainer>
                    {/* Inner Donut Text */}
                    <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                        <span className="text-[10px] uppercase tracking-widest mt-4" style={{ color: "#5C6478" }}>Total</span>
                        <span className="text-sm font-bold font-mono" style={{ color: "#F1F3F6" }}>
                            {formatCurrency(data.reduce((acc, curr) => acc + curr.value, 0))}
                        </span>
                    </div>
                </div>
            )}
        </div>
    );
}
