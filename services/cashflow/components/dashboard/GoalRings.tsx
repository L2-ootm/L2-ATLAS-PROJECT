"use client";

import { formatCurrency } from "@/lib/utils";
import { Target, TrendingUp } from "lucide-react";

interface GoalRingsProps {
    revenue: number;
    expenses: number;
    goal?: number;
}

export default function GoalRings({ revenue, expenses, goal = 50000 }: GoalRingsProps) {
    const profit = revenue - expenses;
    const progress = Math.min((revenue / goal) * 100, 100) || 0;

    const radius = 60;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = circumference - (progress / 100) * circumference;

    const runwayMonths = expenses > 0 ? (profit / expenses).toFixed(1) : "∞";

    return (
        <div data-topo="brand" className="topo-surface topo-shelf goal-panel p-5 relative flex flex-col items-center justify-center">

            <div className="flex w-full justify-between items-start mb-2">
                <div>
                    <h3 className="text-sm font-semibold uppercase tracking-wider flex items-center gap-2" style={{
                        color: "oklch(0.72 0.02 200)",
                        fontFamily: "var(--font-mono)",
                        letterSpacing: "0.12em",
                    }}>
                        <Target className="w-4 h-4" style={{ color: "var(--sig-violet-edge)" }} /> Meta Mensal
                    </h3>
                    <p className="text-xl font-bold font-mono mt-1" style={{ color: "oklch(0.95 0.01 200)" }}>{formatCurrency(goal)}</p>
                </div>
            </div>

            {/* Circular Ring */}
            <div className="relative flex items-center justify-center my-3">
                <svg className="transform -rotate-90 w-36 h-36" viewBox="0 0 160 160">
                    <circle
                        cx="80" cy="80" r={radius}
                        stroke="oklch(1 0 0 / 5%)"
                        strokeWidth="8" fill="transparent"
                    />
                    <circle
                        cx="80" cy="80" r={radius}
                        stroke={progress >= 100 ? "var(--emerald-core)" : "var(--sig-violet-edge)"}
                        strokeWidth="8" fill="transparent"
                        strokeDasharray={circumference}
                        strokeDashoffset={strokeDashoffset}
                        className="transition-all duration-1000 ease-out"
                        strokeLinecap="round"
                        style={{
                            filter: `drop-shadow(0 0 6px ${progress >= 100 ? 'var(--emerald-glow)' : 'rgba(161,123,255,0.3)'})`,
                        }}
                    />
                </svg>

                <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                    <span className="text-3xl font-bold" style={{ color: "oklch(0.95 0.01 200)" }}>
                        {progress.toFixed(0)}<span className="text-lg" style={{ color: "oklch(0.50 0.02 200)" }}>%</span>
                    </span>
                    <span className="text-[10px] uppercase tracking-widest mt-0.5" style={{
                        color: "oklch(0.72 0.02 200)",
                        fontFamily: "var(--font-mono)",
                    }}>Atingido</span>
                </div>
            </div>

            <div className="goal-summary w-full grid grid-cols-2 gap-4 mt-1 pt-4" style={{
                borderTop: "1px solid oklch(1 0 0 / 5%)"
            }}>
                <div className="flex flex-col">
                    <span className="text-[10px] uppercase tracking-wider" style={{ color: "oklch(0.50 0.02 200)" }}>Cobertura Mensal</span>
                    <div className="flex items-center gap-1.5 mt-0.5">
                        <TrendingUp className="w-3.5 h-3.5" style={{ color: "var(--emerald-core)" }} />
                        <span className="text-sm font-mono font-bold" style={{ color: "oklch(0.95 0.01 200)" }}>{runwayMonths} meses</span>
                    </div>
                </div>
                <div className="flex min-w-0 flex-col text-right">
                    <span className="text-[10px] uppercase tracking-wider" style={{ color: "oklch(0.50 0.02 200)" }}>Falta para Meta</span>
                    <span className="text-sm font-mono font-bold mt-0.5 break-words" style={{ color: revenue >= goal ? "var(--emerald-core)" : "var(--sig-crimson)" }}>
                        {revenue >= goal ? "Atingida" : formatCurrency(goal - revenue)}
                    </span>
                </div>
            </div>
        </div>
    );
}
