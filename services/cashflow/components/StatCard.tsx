"use client";

import { LucideIcon } from "lucide-react";

interface StatCardProps {
    title: string;
    value: string;
    icon: LucideIcon;
    trend?: { value: string; positive: boolean };
    accentColor?: "violet" | "red" | "yellow" | "cyan" | "primary" | "success" | "danger" | "warning";
}

// Semantic terrain context per accent — the ambient TopoField glows with this
// meaning when the cursor rests on the card.
const TOPO: Record<string, string> = {
    violet: "brand", primary: "info", cyan: "good", success: "good",
    red: "bad", danger: "bad", yellow: "warn", warning: "warn",
};

export default function StatCard({
    title,
    value,
    icon: Icon,
    trend,
    accentColor = "primary",
}: StatCardProps) {
    return (
        <div
            className={`stat-card stat-${accentColor}`}
            data-topo={TOPO[accentColor] || "info"}
            style={{
                padding: "20px 22px 18px 22px",
            }}
        >
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 14 }}>
                <p style={{
                    fontSize: 11, color: "oklch(0.72 0.02 200)", fontWeight: 500,
                    textTransform: "uppercase", letterSpacing: "0.12em",
                    fontFamily: "var(--font-sans)",
                }}>
                    {title}
                </p>
                <div className="stat-icon-bg" style={{ padding: 7, borderRadius: 4 }}>
                    <Icon className="stat-icon" style={{ width: 15, height: 15 }} />
                </div>
            </div>
            <p style={{
                fontSize: 26, fontWeight: 700, color: "oklch(0.95 0.01 200)", lineHeight: 1.1,
                fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums",
            }}>
                {value}
            </p>
            {trend && (
                <p style={{
                    fontSize: 12, marginTop: 8, fontWeight: 500,
                    color: trend.positive ? "var(--emerald-core)" : "var(--sig-crimson)",
                    fontFamily: "var(--font-mono)",
                }}>
                    {trend.positive ? "↑" : "↓"} {trend.value}
                </p>
            )}
        </div>
    );
}
