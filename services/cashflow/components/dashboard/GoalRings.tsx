"use client";

import { useEffect, useState } from "react";
import { formatCurrency } from "@/lib/utils";
import { Target, TrendingUp } from "lucide-react";

interface GoalRingsProps {
    revenue: number;
    expenses: number;
    goal?: number;
}

export default function GoalRings({ revenue, expenses, goal = 50000 }: GoalRingsProps) {
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    const profit = revenue - expenses;
    const progress = Math.min((revenue / goal) * 100, 100) || 0;

    // SVG Circular calculations
    const radius = 60;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = mounted ? circumference - (progress / 100) * circumference : circumference;

    // Runway calculation (quanto tempo dura o lucro cobrindo as despesas mensais atuais)
    const runwayMonths = expenses > 0 ? (profit / expenses).toFixed(1) : "∞";

    return (
        <div className="l2-border rounded-xl p-6 relative flex flex-col items-center justify-center min-h-[280px]"
            style={{ background: "#1A1D26" }}>

            <div className="flex w-full justify-between items-start mb-2">
                <div>
                    <h3 className="text-sm font-semibold uppercase tracking-wider flex items-center gap-2" style={{ color: "#9CA3B4" }}>
                        <Target className="w-4 h-4" style={{ color: "#6366F1" }} /> Meta Mensal
                    </h3>
                    <p className="text-xl font-bold font-mono mt-1" style={{ color: "#F1F3F6" }}>{formatCurrency(goal)}</p>
                </div>
            </div>

            {/* Circular Ring */}
            <div className="relative flex items-center justify-center my-4">
                <svg className="transform -rotate-90 w-40 h-40">
                    {/* Background Track */}
                    <circle
                        cx="80"
                        cy="80"
                        r={radius}
                        stroke="#252937"
                        strokeWidth="8"
                        fill="transparent"
                    />
                    {/* Progress Ring */}
                    <circle
                        cx="80"
                        cy="80"
                        r={radius}
                        stroke={progress >= 100 ? "#34D399" : "#6366F1"}
                        strokeWidth="8"
                        fill="transparent"
                        strokeDasharray={circumference}
                        strokeDashoffset={strokeDashoffset}
                        className="transition-all duration-1000 ease-out"
                        strokeLinecap="round"
                    />
                </svg>

                <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                    <span className="text-3xl font-bold" style={{ color: "#F1F3F6" }}>
                        {mounted ? progress.toFixed(0) : 0}<span className="text-lg" style={{ color: "#5C6478" }}>%</span>
                    </span>
                    <span className="text-[10px] uppercase tracking-widest mt-0.5" style={{ color: "#9CA3B4" }}>Atingido</span>
                </div>
            </div>

            <div className="w-full flex justify-between items-center px-2 mt-2 pt-4" style={{ borderTop: "1px solid #2E3340" }}>
                <div className="flex flex-col">
                    <span className="text-[10px] uppercase tracking-wider" style={{ color: "#5C6478" }}>Cobertura Mensal</span>
                    <div className="flex items-center gap-1.5 mt-0.5">
                        <TrendingUp className="w-3.5 h-3.5" style={{ color: "#34D399" }} />
                        <span className="text-sm font-mono font-bold" style={{ color: "#F1F3F6" }}>{runwayMonths} meses</span>
                    </div>
                </div>
                <div className="flex flex-col text-right">
                    <span className="text-[10px] uppercase tracking-wider" style={{ color: "#5C6478" }}>Falta para Meta</span>
                    <span className="text-sm font-mono font-bold mt-0.5" style={{ color: revenue >= goal ? "#34D399" : "#F87171" }}>
                        {revenue >= goal ? "Batida!" : formatCurrency(goal - revenue)}
                    </span>
                </div>
            </div>
        </div>
    );
}
