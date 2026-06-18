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
        <div className="flex items-center gap-3 rounded-lg px-2 py-1.5" style={{ background: "#1A1D26", border: "1px solid #2E3340" }}>
            <button
                onClick={() => navigate(-1)}
                className="p-1.5 rounded-md transition-colors"
                style={{ color: "#9CA3B4" }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "#252937"; e.currentTarget.style.color = "#F1F3F6"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "#9CA3B4"; }}
            >
                <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-sm font-semibold min-w-[140px] text-center" style={{ color: "#F1F3F6" }}>
                {getMonthLabel(value)}
            </span>
            <button
                onClick={() => navigate(1)}
                className="p-1.5 rounded-md transition-colors"
                style={{ color: "#9CA3B4" }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "#252937"; e.currentTarget.style.color = "#F1F3F6"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "#9CA3B4"; }}
            >
                <ChevronRight className="w-4 h-4" />
            </button>
        </div>
    );
}
