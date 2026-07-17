"use client";

import { useState, useEffect, useMemo } from "react";
import { Briefcase, AlertTriangle, Users, Clock, CheckCircle2 } from "lucide-react";
import StatCard from "@/components/StatCard";
import { getClients } from "@/app/actions";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Client } from "@/lib/types";

export default function ContratosPage() {
    const [clients, setClients] = useState<Client[]>([]);

    useEffect(() => {
        getClients().then(setClients);
    }, []);

    const activeClients = useMemo(() => clients.filter(c => c.active), [clients]);
    const contractsData = useMemo(() => {
        const today = new Date();
        return activeClients.map(c => {
            if (!c.contractMonths || c.contractMonths === 0) {
                return { ...c, status: "recorrente", endDate: null, daysRemaining: null };
            }
            const end = new Date(c.startDate);
            end.setMonth(end.getMonth() + c.contractMonths);
            const daysRemaining = Math.ceil((end.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));

            let status = "ativo";
            if (daysRemaining <= 0) status = "vencido";
            else if (daysRemaining <= 30) status = "atencao";

            return { ...c, endDate: end.toISOString().split("T")[0], daysRemaining, status };
        }).sort((a, b) => {
            if (a.status === "vencido" && b.status !== "vencido") return -1;
            if (b.status === "vencido" && a.status !== "vencido") return 1;
            if (a.status === "atencao" && b.status !== "atencao") return -1;
            if (b.status === "atencao" && a.status !== "atencao") return 1;
            return 0;
        });
    }, [activeClients]);

    const stats = useMemo(() => {
        let recorrente = 0;
        let atencao = 0;
        let vencidos = 0;
        let totalReceitaFidelizada = 0;

        contractsData.forEach(c => {
            if (c.status === "recorrente") recorrente++;
            if (c.status === "atencao") atencao++;
            if (c.status === "vencido") vencidos++;
            if (c.status !== "recorrente") totalReceitaFidelizada += c.monthlyPayment;
        });

        return { recorrente, atencao, vencidos, totalReceitaFidelizada };
    }, [contractsData]);

    const getStatusBadge = (status: string, days?: number | null) => {
        if (status === "recorrente") {
            return (
                <span style={{
                    display: "inline-block", padding: "4px 10px", borderRadius: 6,
                    fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em",
                    background: "rgba(79,139,255,0.1)", color: "var(--atlas-celestial)",
                }}>
                    Mensal
                </span>
            );
        }
        if (status === "vencido") {
            return (
                <span style={{
                    display: "inline-flex", alignItems: "center", gap: 4, padding: "4px 10px", borderRadius: 6,
                    fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em",
                    background: "rgba(248,113,113,0.1)", color: "var(--sig-crimson)",
                }}>
                    <AlertTriangle style={{ width: 12, height: 12 }} /> Vencido
                </span>
            );
        }
        if (status === "atencao") {
            return (
                <span style={{
                    display: "inline-flex", alignItems: "center", gap: 4, padding: "4px 10px", borderRadius: 6,
                    fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em",
                    background: "rgba(251,191,36,0.1)", color: "var(--sig-amber)",
                }}>
                    <Clock style={{ width: 12, height: 12 }} /> Renovar ({days}d)
                </span>
            );
        }
        return (
            <span style={{
                display: "inline-flex", alignItems: "center", gap: 4, padding: "4px 10px", borderRadius: 6,
                fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em",
                background: "rgba(52,211,153,0.1)", color: "var(--atlas-cyan)",
            }}>
                <CheckCircle2 style={{ width: 12, height: 12 }} /> Ativo
            </span>
        );
    };

    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
                <div>
                    <h1 className="text-2xl font-bold" style={{ color: "var(--l2-fg-1)" }}>Contratos</h1>
                    <p className="text-sm mt-0.5" style={{ color: "var(--l2-fg-3)" }}>Monitoramento de vigência e retenção</p>
                </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard title="Receita Fidelizada" value={formatCurrency(stats.totalReceitaFidelizada)} icon={Briefcase} accentColor="violet" />
                <StatCard title="Renovar em Breve" value={String(stats.atencao)} icon={Clock} accentColor="yellow"
                    trend={stats.atencao > 0 ? { value: "Ação necessária", positive: false } : undefined} />
                <StatCard title="Contratos Vencidos" value={String(stats.vencidos)} icon={AlertTriangle} accentColor="red" />
                <StatCard title="Sem Fidelidade (Mensal)" value={String(stats.recorrente)} icon={Users} accentColor="cyan" />
            </div>

            {/* Table */}
            <div className="l2-border" style={{ borderRadius: 12, overflow: "hidden", background: "rgba(24,28,38,0.55)" }}>
                <div style={{
                    display: "grid", gridTemplateColumns: "1fr 2fr 1fr 1fr 1fr 1fr",
                    padding: "14px 24px", borderBottom: "1px solid var(--l2-hairline)", background: "rgba(18,21,29,0.65)",
                }}>
                    <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: "var(--l2-fg-3)" }}>Status</span>
                    <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: "var(--l2-fg-3)" }}>Cliente</span>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-right" style={{ color: "var(--l2-fg-3)" }}>Valor Mensal</span>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-center" style={{ color: "var(--l2-fg-3)" }}>Início</span>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-center" style={{ color: "var(--l2-fg-3)" }}>Vencimento</span>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-right" style={{ color: "var(--l2-fg-3)" }}>Prazo Total</span>
                </div>

                {contractsData.length === 0 ? (
                    <div style={{ padding: "48px 24px", textAlign: "center" }}>
                        <p className="text-sm" style={{ color: "var(--l2-fg-3)" }}>Nenhum contrato ativo.</p>
                    </div>
                ) : (
                    contractsData.map((contract, i) => (
                        <div key={contract.id} style={{
                            display: "grid", gridTemplateColumns: "1fr 2fr 1fr 1fr 1fr 1fr",
                            padding: "16px 24px", alignItems: "center",
                            borderBottom: i < contractsData.length - 1 ? "1px solid rgba(34,40,56,0.65)" : "none",
                            transition: "background 150ms",
                        }}
                            onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(18,21,29,0.65)"; }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                        >
                            <div>{getStatusBadge(contract.status, contract.daysRemaining)}</div>
                            <div>
                                <span className="text-sm font-semibold block truncate" style={{ color: "var(--l2-fg-1)" }}>{contract.name}</span>
                                <span className="text-[10px] font-mono uppercase" style={{ color: "var(--l2-fg-2)" }}>{contract.service}</span>
                            </div>
                            <span className="text-sm font-mono font-semibold text-right" style={{ color: "var(--l2-fg-1)" }}>{formatCurrency(contract.monthlyPayment)}</span>
                            <span className="text-sm font-mono text-center" style={{ color: "var(--l2-fg-2)" }}>{formatDate(contract.startDate)}</span>
                            <span className="text-sm font-mono text-center font-semibold" style={{ color: contract.status === "recorrente" ? "var(--l2-fg-3)" : contract.status === "vencido" ? "var(--sig-crimson)" : contract.status === "atencao" ? "var(--sig-amber)" : "var(--l2-fg-1)" }}>
                                {contract.endDate ? formatDate(contract.endDate) : "—"}
                            </span>
                            <span className="text-sm text-right" style={{ color: "var(--l2-fg-2)" }}>
                                {contract.status === "recorrente" ? "Indeterminado" : `${contract.contractMonths} meses`}
                            </span>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
