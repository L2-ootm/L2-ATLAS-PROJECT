"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { getMonthLabel } from "@/lib/utils";

interface MonthSelectorProps {
    value: string;
    onChange: (value: string) => void;
}

export default function MonthSelector({ value, onChange }: MonthSelectorProps) {
    const navigate = (delta: number) => {
        const [year, month] = value.split("-").map(Number);
        const date = new Date(year, month - 1 + delta, 1);
        const newValue = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
        onChange(newValue);
    };

    return (
        <div className="topo-surface flex items-center gap-3 px-3 py-2">
            <button
                onClick={() => navigate(-1)}
                className="p-1.5 rounded-sm transition-all"
                style={{ color: "oklch(0.72 0.02 200)" }}
                onMouseEnter={(e) => {
                    e.currentTarget.style.background = "oklch(1 0 0 / 5%)";
                    e.currentTarget.style.color = "oklch(0.95 0.01 200)";
                }}
                onMouseLeave={(e) => {
                    e.currentTarget.style.background = "transparent";
                    e.currentTarget.style.color = "oklch(0.72 0.02 200)";
                }}
            >
                <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-sm font-semibold min-w-[140px] text-center" style={{
                color: "oklch(0.95 0.01 200)",
                fontFamily: "var(--font-mono)",
                letterSpacing: "0.05em",
            }}>
                {getMonthLabel(value)}
            </span>
            <button
                onClick={() => navigate(1)}
                className="p-1.5 rounded-sm transition-all"
                style={{ color: "oklch(0.72 0.02 200)" }}
                onMouseEnter={(e) => {
                    e.currentTarget.style.background = "oklch(1 0 0 / 5%)";
                    e.currentTarget.style.color = "oklch(0.95 0.01 200)";
                }}
                onMouseLeave={(e) => {
                    e.currentTarget.style.background = "transparent";
                    e.currentTarget.style.color = "oklch(0.72 0.02 200)";
                }}
            >
                <ChevronRight className="w-4 h-4" />
            </button>
        </div>
    );
}
