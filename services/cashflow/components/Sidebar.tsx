"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Users, Receipt, BarChart3, Menu, X, Wallet, FileText, Briefcase, Landmark, LineChart, Search, CreditCard, Gauge, FileBarChart, ShieldCheck, Globe } from "lucide-react";
import { useState } from "react";

const navigation = [
    { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    { name: "Clientes", href: "/clientes", icon: Users },
    { name: "Contratos", href: "/contratos", icon: Briefcase },
    { name: "Enterprise P&L", href: "/enterprise/pnl", icon: LineChart },
    { name: "AI Cost Explorer", href: "/enterprise/explorer", icon: Search },
    { name: "Pesquisa & ROI", href: "/enterprise/research", icon: Globe },
    { name: "Billing Plus", href: "/enterprise/billing", icon: CreditCard },
    { name: "Forecast & Alertas", href: "/enterprise/forecast", icon: Gauge },
    { name: "Relatórios IA", href: "/enterprise/reports", icon: FileBarChart },
    { name: "Auditoria", href: "/enterprise/audit", icon: ShieldCheck },
    { name: "Faturas", href: "/faturas", icon: FileText },
    { name: "Despesas", href: "/despesas", icon: Receipt },
    { name: "Fluxo de Caixa", href: "/fluxo-caixa", icon: Wallet },
    { name: "Caixa L2 & Sócios", href: "/socios", icon: Landmark },
    { name: "Relatórios", href: "/relatorios", icon: BarChart3 },
];

export default function Sidebar() {
    const pathname = usePathname();
    const [mobileOpen, setMobileOpen] = useState(false);

    return (
        <>
            {/* Mobile toggle */}
            <button
                onClick={() => setMobileOpen(!mobileOpen)}
                style={{
                    position: "fixed", top: 16, left: 16, zIndex: 50,
                    padding: 10, borderRadius: 8, background: "#1A1D26", color: "#F1F3F6",
                    border: "1px solid #2E3340", cursor: "pointer",
                    display: "none",
                }}
                className="mobile-menu-btn"
            >
                {mobileOpen ? <X size={22} /> : <Menu size={22} />}
            </button>

            {/* Sidebar */}
            <aside
                style={{
                    width: 256,
                    flexShrink: 0,
                    background: "#141720",
                    borderRight: "1px solid #2E3340",
                    display: "flex",
                    flexDirection: "column",
                    position: "relative",
                }}
                className="sidebar-wrapper"
            >
                {/* Logo */}
                <div style={{
                    height: 64, display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
                    borderBottom: "1px solid #2E3340",
                }}>
                    <div style={{
                        width: 36, height: 36, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center",
                        background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.2)",
                    }}>
                        <span style={{ color: "#6366F1", fontWeight: 700, fontSize: 14 }}>L2</span>
                    </div>
                    <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: "#F1F3F6" }}>
                        <span style={{ color: "#9CA3B4", fontWeight: 400 }}>Financeiro</span>
                    </h1>
                </div>

                {/* Navigation */}
                <nav style={{ padding: 16, display: "flex", flexDirection: "column", gap: 2, flex: 1 }}>
                    {navigation.map((item) => {
                        const isActive = pathname === item.href || pathname?.startsWith(item.href + "/");
                        return (
                            <Link
                                key={item.name}
                                href={item.href}
                                onClick={() => setMobileOpen(false)}
                                style={{
                                    display: "flex", alignItems: "center", gap: 12,
                                    padding: "10px 14px", borderRadius: 8,
                                    textDecoration: "none",
                                    color: isActive ? "#6366F1" : "#9CA3B4",
                                    background: isActive ? "rgba(99,102,241,0.1)" : "transparent",
                                    border: isActive ? "1px solid rgba(99,102,241,0.18)" : "1px solid transparent",
                                    fontSize: 14, fontWeight: isActive ? 600 : 500,
                                    transition: "background 150ms, color 150ms",
                                }}
                                onMouseEnter={(e) => {
                                    if (!isActive) {
                                        e.currentTarget.style.background = "#1F2230";
                                        e.currentTarget.style.color = "#F1F3F6";
                                    }
                                }}
                                onMouseLeave={(e) => {
                                    if (!isActive) {
                                        e.currentTarget.style.background = "transparent";
                                        e.currentTarget.style.color = "#9CA3B4";
                                    }
                                }}
                            >
                                <item.icon style={{ width: 20, height: 20, flexShrink: 0 }} />
                                <span>{item.name}</span>
                            </Link>
                        );
                    })}
                </nav>

                {/* Footer */}
                <div style={{
                    padding: 16, borderTop: "1px solid #2E3340",
                    textAlign: "center",
                }}>
                    <p style={{ fontSize: 11, color: "#5C6478", letterSpacing: "0.05em", textTransform: "uppercase" }} className="font-mono">
                        © 2026 L2 Systems
                    </p>
                </div>
            </aside>

            {/* Mobile overlay */}
            {mobileOpen && (
                <div
                    style={{ position: "fixed", inset: 0, zIndex: 30, background: "rgba(0,0,0,0.6)" }}
                    onClick={() => setMobileOpen(false)}
                />
            )}

            {/* Responsive: hide sidebar on mobile, show menu btn */}
            <style>{`
        @media (max-width: 1023px) {
          .sidebar-wrapper {
            position: fixed !important;
            top: 0; left: 0; bottom: 0;
            z-index: 40;
            transform: ${mobileOpen ? "translateX(0)" : "translateX(-100%)"};
            transition: transform 200ms ease-out;
          }
          .mobile-menu-btn { display: block !important; }
        }
      `}</style>
        </>
    );
}
