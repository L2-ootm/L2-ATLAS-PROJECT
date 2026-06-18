"use client";

import { LucideIcon } from "lucide-react";
import { useState, useEffect } from "react";

interface StatCardProps {
    title: string;
    value: string;
    icon: LucideIcon;
    trend?: { value: string; positive: boolean };
    accentColor?: "violet" | "red" | "yellow" | "cyan" | "primary" | "success" | "danger" | "warning";
}

export default function StatCard({
    title,
    value,
    icon: Icon,
    trend,
    accentColor = "primary",
}: StatCardProps) {
    const [displayValue, setDisplayValue] = useState(value);

    useEffect(() => {
        const isNumeric = /[0-9]/.test(value);
        if (isNumeric) {
            setDisplayValue(value);
        }
    }, [value]);

    return (
        <div
            className={`stat-${accentColor}`}
            style={{
                borderRadius: 10,
                padding: "20px 22px 18px 22px",
                transition: "border-color 200ms ease",
            }}
        >
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 14 }}>
                <p style={{ fontSize: 12, color: "#9CA3B4", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                    {title}
                </p>
                <div className="stat-icon-bg" style={{ padding: 8, borderRadius: 8 }}>
                    <Icon className="stat-icon" style={{ width: 16, height: 16 }} />
                </div>
            </div>
            <p style={{ fontSize: 26, fontWeight: 700, color: "#F1F3F6", lineHeight: 1.1 }} className="font-mono">
                {displayValue}
            </p>
            {trend && (
                <p style={{ fontSize: 12, marginTop: 8, fontWeight: 500, color: trend.positive ? "#34D399" : "#F87171" }} className="font-mono">
                    {trend.positive ? "↑" : "↓"} {trend.value}
                </p>
            )}
        </div>
    );
}
