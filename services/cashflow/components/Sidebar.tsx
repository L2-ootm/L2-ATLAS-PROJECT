"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Users, Receipt, BarChart3, Menu, X, Wallet, FileText, Briefcase, Landmark, LineChart, Search, CreditCard, Gauge, FileBarChart, ShieldCheck, Globe } from "lucide-react";
import { useState } from "react";
import AtlasMark from "./AtlasMark";

const ATLAS_COCKPIT_URL = process.env.NEXT_PUBLIC_ATLAS_URL || "http://localhost:5173";

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
                className="mobile-menu-btn"
                style={{
                    position: "fixed", top: 16, left: 16, zIndex: 50,
                    padding: 10, borderRadius: 2,
                    background: "rgba(7,8,12,0.85)", color: "var(--l2-fg-1)",
                    border: "1px solid rgba(79,139,255,0.20)",
                    cursor: "pointer",
                    backdropFilter: "blur(16px) saturate(140%)",
                    boxShadow: "0 0 12px rgba(79,139,255,0.08)",
                    display: "none",
                    transition: "box-shadow 0.25s cubic-bezier(0.22, 1, 0.36, 1)",
                }}
            >
                {mobileOpen ? <X size={20} /> : <Menu size={20} />}
            </button>

            {/* Sidebar — Topographic glassmorphism */}
            <aside className={`sidebar-wrapper ${mobileOpen ? "open" : ""}`}>
                {/* Header — Atlas brand */}
                <div style={{
                    height: 72, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10,
                    padding: "0 18px",
                    borderBottom: "1px solid var(--l2-hairline)",
                }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                        <AtlasMark size={30} title="ATLAS" />
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
                            <h1 style={{
                                fontSize: "1rem", fontWeight: 700, margin: 0, color: "var(--l2-fg-1)",
                                lineHeight: 1, letterSpacing: "0.3em", textTransform: "uppercase",
                                fontFamily: "var(--font-sans)",
                            }}>
                                ATLAS
                            </h1>
                            <span style={{ color: "var(--l2-fg-3)", fontWeight: 400, fontSize: "0.5rem", letterSpacing: "0.3em", textTransform: "uppercase", fontFamily: "var(--font-mono)" }}>
                                CASHFLOW
                            </span>
                        </div>
                    </div>
                    <a
                        href={`${ATLAS_COCKPIT_URL}/cashflow`}
                        target="_top"
                        className="topo-btn topo-btn--muted"
                        style={{
                            padding: "4px 8px",
                            fontSize: 8,
                            letterSpacing: "0.14em",
                            textDecoration: "none",
                            whiteSpace: "nowrap",
                        }}
                    >
                        ← Atlas
                    </a>
                </div>

                {/* Navigation — topo-glow links */}
                <nav data-topo="info" style={{
                    padding: "8px 0",
                    display: "flex", flexDirection: "column", gap: 0, flex: 1,
                    overflowY: "auto", overflowX: "hidden",
                }}>
                    <ul role="list" style={{ listStyle: "none", margin: 0, padding: 0 }}>
                    {navigation.map((item) => {
                        const isActive = pathname === item.href || pathname?.startsWith(item.href + "/");
                        return (
                            <li key={item.name}>
                            <Link
                                href={item.href}
                                onClick={() => setMobileOpen(false)}
                                className={isActive ? "topo-nav-active" : "topo-nav-link"}
                                style={{
                                    position: "relative",
                                    display: "flex", alignItems: "center", gap: 14,
                                    padding: "0 12px",
                                    height: 46,
                                    margin: "2px 8px",
                                    borderRadius: "var(--topo-r-sys)",
                                    textDecoration: "none",
                                    transition: "all 0.25s cubic-bezier(0.22, 1, 0.36, 1)",
                                    whiteSpace: "nowrap",
                                    ...(isActive
                                        ? {
                                            background: "rgba(79,139,255,0.10)",
                                            color: "var(--atlas-celestial)",
                                            boxShadow: "inset 2px 0 0 0 rgba(79,139,255,0.70), 0 0 16px rgba(79,139,255,0.12)",
                                          }
                                        : {
                                            background: "transparent",
                                            color: "var(--l2-fg-3)",
                                          }),
                                }}
                                onMouseEnter={(e) => {
                                    if (!isActive) {
                                        e.currentTarget.style.background = "oklch(1 0 0 / 3%)";
                                        e.currentTarget.style.color = "oklch(0.95 0.01 200)";
                                    }
                                }}
                                onMouseLeave={(e) => {
                                    if (!isActive) {
                                        e.currentTarget.style.background = "transparent";
                                        e.currentTarget.style.color = "oklch(0.50 0.02 200)";
                                    }
                                }}
                            >
                                {/* Active left accent bar — signal-cyan glow */}
                                {isActive && (
                                    <span
                                        aria-hidden
                                        style={{
                                            position: "absolute",
                                            left: -8,
                                            top: "50%",
                                            transform: "translateY(-50%)",
                                            width: 3,
                                            height: 22,
                                            borderRadius: "0 2px 2px 0",
                                            background: "var(--emerald-core)",
                                            boxShadow: "0 0 12px var(--emerald-glow)",
                                        }}
                                    />
                                )}
                                <item.icon size={17} strokeWidth={1.5} color="currentColor" style={{ flexShrink: 0 }} />
                                <span style={{
                                    fontFamily: "var(--font-mono)",
                                    fontSize: 12,
                                    fontWeight: 500,
                                    textTransform: "uppercase",
                                    letterSpacing: "0.16em",
                                }}>
                                    {item.name}
                                </span>
                            </Link>
                            </li>
                        );
                    })}
                    </ul>
                </nav>

                {/* Footer — topo system status */}
                <div style={{
                    padding: "14px 18px",
                    borderTop: "1px solid var(--l2-hairline)",
                    display: "flex", flexDirection: "column", gap: 10,
                }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span aria-hidden style={{
                            width: 7, height: 7, borderRadius: "50%",
                            background: "var(--emerald-core)",
                            boxShadow: "0 0 8px var(--emerald-glow)",
                            animation: "topo-glow-pulse 3s ease-in-out infinite",
                        }} />
                        <span style={{
                            fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase",
                            letterSpacing: "0.16em", color: "var(--emerald-core)"
                        }}>
                            SERVER · ONLINE
                        </span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--l2-fg-3)" }}>
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="var(--atlas-bronze)" strokeWidth="3" strokeLinecap="square">
                            <path d="M5 5 V19 H13 M15 5 H19 V11 H15 V19 H19" />
                        </svg>
                        <span style={{ fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase" }}>
                            BY L2 SYSTEMS
                        </span>
                    </div>
                </div>
            </aside>

            {/* Mobile overlay */}
            {mobileOpen && (
                <div
                    style={{ position: "fixed", inset: 0, zIndex: 30, background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
                    onClick={() => setMobileOpen(false)}
                />
            )}

            {/* Responsive styles handled by globals.css media query */}
        </>
    );
}
