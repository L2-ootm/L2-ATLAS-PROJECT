"use client";

import { useState, useEffect, useMemo } from "react";
import { Wallet, ArrowUpRight, ArrowDownRight } from "lucide-react";
import {
    getPartnerWallets,
    getPartnerTransactions,
    addPartnerTransaction,
    getInvoices,
    getExpenses
} from "@/app/actions";
import { formatCurrency, formatDate, generateId } from "@/lib/utils";
import { PartnerWallet, PartnerTransaction } from "@/lib/types";

export default function SociosDashboard() {
    const [wallets, setWallets] = useState<PartnerWallet[]>([]);
    const [transactions, setTransactions] = useState<PartnerTransaction[]>([]);

    const [modalMode, setModalMode] = useState<"injection" | "withdrawal" | null>(null);
    const [amountStr, setAmountStr] = useState("");
    const [desc, setDesc] = useState("");

    // For injection
    const [splitType, setSplitType] = useState<"50-50" | "custom">("50-50");
    const [arturPct, setArturPct] = useState(50);
    const [daviPct, setDaviPct] = useState(50);

    // For withdrawal
    const [selectedPartner, setSelectedPartner] = useState("");

    // Financial calculations
    const [netProfit, setNetProfit] = useState(0);

    useEffect(() => {
        refreshData();
    }, []);

    const refreshData = async () => {
        setWallets(await getPartnerWallets());

        const txs = await getPartnerTransactions();
        setTransactions(txs.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()));

        const allInvoices = await getInvoices();
        const paidInvoices = allInvoices.filter((i: any) => i.status === "pago").reduce((s: number, i: any) => s + i.amount, 0);
        const allExpenses = await getExpenses();
        const totalExp = allExpenses.reduce((s: number, e: any) => s + e.amount, 0);
        setNetProfit(paidInvoices - totalExp);
    };

    const totalDistributed = useMemo(() => {
        return transactions
            .filter(t => t.type === "injection")
            .reduce((s, t) => s + t.amount, 0);
    }, [transactions]);

    const availableToDistribute = Math.max(0, netProfit - totalDistributed);

    // Handle 50/50 toggles
    useEffect(() => {
        if (splitType === "50-50") {
            setArturPct(50);
            setDaviPct(50);
        }
    }, [splitType]);

    const handleAction = async (e: React.FormEvent) => {
        e.preventDefault();
        const amt = parseFloat(amountStr);
        if (isNaN(amt) || amt <= 0) return;

        const date = new Date().toISOString();

        if (modalMode === "injection") {
            const arturAmount = amt * (arturPct / 100);
            const daviAmount = amt * (daviPct / 100);

            if (arturAmount > 0) {
                await addPartnerTransaction({
                    id: generateId(),
                    partnerId: "artur",
                    type: "injection",
                    amount: arturAmount,
                    date,
                    description: desc || "Distribuição de Lucro L2"
                });
            }
            if (daviAmount > 0) {
                await addPartnerTransaction({
                    id: generateId(),
                    partnerId: "davi",
                    type: "injection",
                    amount: daviAmount,
                    date,
                    description: desc || "Distribuição de Lucro L2"
                });
            }
        } else if (modalMode === "withdrawal") {
            if (!selectedPartner) return;
            await addPartnerTransaction({
                id: generateId(),
                partnerId: selectedPartner,
                type: "withdrawal",
                amount: amt,
                date,
                description: desc || "Retirada de Sócio"
            });
        }

        closeModal();
        await refreshData();
    };

    const closeModal = () => {
        setModalMode(null);
        setAmountStr("");
        setDesc("");
        setSelectedPartner("");
        setSplitType("50-50");
    };

    const getWallet = (id: string) => wallets.find(w => w.id === id);
    const arturWallet = getWallet("artur");
    const daviWallet = getWallet("davi");

    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
                <div>
                    <h1 className="text-2xl font-bold" style={{ color: "var(--l2-fg-1)" }}>Caixa L2 & Sócios</h1>
                    <p className="text-sm mt-0.5" style={{ color: "var(--l2-fg-3)" }}>Gestão de lucros e carteiras dos fundadores</p>
                </div>
                <div style={{ display: "flex", gap: 12 }}>
                    <button
                        data-topo="bad"
                        onClick={() => { setModalMode("withdrawal"); setDesc("Retirada"); }}
                        style={{
                            display: "flex", alignItems: "center", gap: 8,
                            padding: "10px 20px", borderRadius: 8,
                            background: "rgba(248,113,113,0.1)", color: "var(--sig-crimson)", fontWeight: 600, fontSize: 13,
                            border: "1px solid rgba(248,113,113,0.2)", cursor: "pointer",
                            transition: "all 200ms",
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(248,113,113,0.15)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(248,113,113,0.1)"; }}
                    >
                        <ArrowDownRight style={{ width: 16, height: 16 }} />
                        Realizar Retirada
                    </button>
                    <button
                        onClick={() => { setModalMode("injection"); setDesc("Distribuição Ref. Mês"); }}
                        style={{
                            display: "flex", alignItems: "center", gap: 8,
                            padding: "10px 24px", borderRadius: 8,
                            background: "rgba(79,139,255,0.14)", color: "var(--atlas-celestial-soft)", fontWeight: 600, fontSize: 14,
                            border: "1px solid rgba(79,139,255,0.38)", cursor: "pointer",
                            boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                            transition: "all 200ms",
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(79,139,255,0.24)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(79,139,255,0.14)"; }}
                    >
                        <ArrowUpRight style={{ width: 18, height: 18 }} />
                        Injetar Lucro
                    </button>
                </div>
            </div>

            {/* Wallets & Global Stats */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
                {/* L2 Global */}
                <div className="l2-border" style={{ borderRadius: 16, padding: 24, display: "flex", flexDirection: "column", gap: 16, background: "rgba(24,28,38,0.55)" }}>
                    <div className="flex items-center gap-3">
                        <div style={{ padding: 10, borderRadius: 8, background: "rgba(79,139,255,0.1)", color: "var(--atlas-celestial)" }}>
                            <Wallet className="w-5 h-5" />
                        </div>
                        <span className="text-sm font-semibold" style={{ color: "var(--l2-fg-2)" }}>Lucro não distribuído</span>
                    </div>
                    <div>
                        <div className="text-3xl font-bold font-mono tracking-tight" style={{ color: "var(--l2-fg-1)" }}>{formatCurrency(availableToDistribute)}</div>
                        <div className="text-xs mt-2" style={{ color: "var(--l2-fg-3)" }}>Lucro Líquido L2: {formatCurrency(netProfit)}</div>
                    </div>
                </div>

                {/* Artur Wallet */}
                <div className="l2-border" style={{ borderRadius: 16, padding: 24, display: "flex", flexDirection: "column", gap: 16, background: "rgba(24,28,38,0.55)" }}>
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full flex items-center justify-center font-bold"
                                style={{ background: "rgba(34,40,56,0.65)", border: "1px solid var(--l2-hairline)", color: "var(--l2-fg-1)" }}>
                                A
                            </div>
                            <span className="text-base font-semibold" style={{ color: "var(--l2-fg-1)" }}>Artur Wallet</span>
                        </div>
                    </div>
                    <div>
                        <div className="text-3xl font-bold font-mono tracking-tight" style={{ color: "var(--atlas-celestial)" }}>{formatCurrency(arturWallet?.balance || 0)}</div>
                        <div className="text-xs mt-2 uppercase tracking-wider" style={{ color: "var(--l2-fg-3)" }}>Saldo Disponível para Saque</div>
                    </div>
                </div>

                {/* Davi Wallet */}
                <div className="l2-border" style={{ borderRadius: 16, padding: 24, display: "flex", flexDirection: "column", gap: 16, background: "rgba(24,28,38,0.55)" }}>
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full flex items-center justify-center font-bold"
                                style={{ background: "rgba(34,40,56,0.65)", border: "1px solid var(--l2-hairline)", color: "var(--l2-fg-1)" }}>
                                D
                            </div>
                            <span className="text-base font-semibold" style={{ color: "var(--l2-fg-1)" }}>Davi Wallet</span>
                        </div>
                    </div>
                    <div>
                        <div className="text-3xl font-bold font-mono tracking-tight" style={{ color: "var(--atlas-celestial)" }}>{formatCurrency(daviWallet?.balance || 0)}</div>
                        <div className="text-xs mt-2 uppercase tracking-wider" style={{ color: "var(--l2-fg-3)" }}>Saldo Disponível para Saque</div>
                    </div>
                </div>
            </div>

            {/* History Table */}
            <div>
                <h3 className="text-lg font-bold mb-4" style={{ color: "var(--l2-fg-1)" }}>Extrato de Sócios</h3>
                <div className="l2-border" style={{ borderRadius: 12, overflow: "hidden", background: "rgba(24,28,38,0.55)" }}>
                    <div style={{
                        display: "grid", gridTemplateColumns: "1fr 1.5fr 2fr 1fr",
                        padding: "14px 24px", borderBottom: "1px solid var(--l2-hairline)", background: "rgba(18,21,29,0.65)"
                    }}>
                        <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: "var(--l2-fg-3)" }}>Data</span>
                        <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: "var(--l2-fg-3)" }}>Operação</span>
                        <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: "var(--l2-fg-3)" }}>Descrição</span>
                        <span className="text-[10px] font-mono uppercase tracking-wider text-right" style={{ color: "var(--l2-fg-3)" }}>Valor</span>
                    </div>

                    {transactions.length === 0 ? (
                        <div style={{ padding: "48px 24px", textAlign: "center" }}>
                            <p className="text-sm" style={{ color: "var(--l2-fg-3)" }}>Nenhuma transação registrada.</p>
                        </div>
                    ) : (
                        transactions.map((tx, i) => (
                            <div key={tx.id} style={{
                                display: "grid", gridTemplateColumns: "1fr 1.5fr 2fr 1fr",
                                padding: "16px 24px", alignItems: "center",
                                borderBottom: i < transactions.length - 1 ? "1px solid rgba(34,40,56,0.65)" : "none",
                            }}>
                                <span className="text-sm font-mono" style={{ color: "var(--l2-fg-2)" }}>{formatDate(tx.date.split('T')[0])}</span>
                                <div className="flex items-center gap-2">
                                    {tx.type === "injection" ? (
                                        <ArrowUpRight className="w-4 h-4" style={{ color: "var(--atlas-cyan)" }} />
                                    ) : (
                                        <ArrowDownRight className="w-4 h-4" style={{ color: "var(--sig-crimson)" }} />
                                    )}
                                    <span className="text-sm capitalize" style={{ color: "var(--l2-fg-1)" }}>
                                        {tx.type === "injection" ? "Injeção" : "Retirada"} ({tx.partnerId})
                                    </span>
                                </div>
                                <span className="text-sm truncate" style={{ color: "var(--l2-fg-2)" }}>{tx.description}</span>
                                <span className="text-sm font-mono font-semibold text-right" style={{ color: tx.type === "injection" ? "var(--atlas-cyan)" : "var(--sig-crimson)" }}>
                                    {tx.type === "injection" ? "+" : "-"}{formatCurrency(tx.amount)}
                                </span>
                            </div>
                        ))
                    )}
                </div>
            </div>

            {/* Modal */}
            {modalMode && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 transition-all" style={{ background: "rgba(0,0,0,0.5)" }} onClick={closeModal}>
                    <div className="animate-l2-enter relative overflow-hidden" style={{ borderRadius: 12, padding: 32, width: "100%", maxWidth: 440, background: "rgba(24,28,38,0.55)", border: "1px solid var(--l2-hairline)", boxShadow: "0 24px 48px rgba(0,0,0,0.4)" }} onClick={(e) => e.stopPropagation()}>
                        <h2 className="text-lg font-bold mb-6" style={{ color: "var(--l2-fg-1)" }}>
                            {modalMode === "injection" ? "Injetar Lucro nas Carteiras" : "Nova Retirada de Sócio"}
                        </h2>

                        <form onSubmit={handleAction} className="flex flex-col gap-5">
                            <div>
                                <label className="block text-xs font-medium uppercase tracking-wider mb-2" style={{ color: "var(--l2-fg-2)" }}>Valor (R$)</label>
                                <input type="number" required min="0.01" step="0.01" value={amountStr} onChange={(e) => setAmountStr(e.target.value)}
                                    className="input-l2 w-full px-4 py-3 rounded-lg font-mono text-lg" placeholder="0,00" />
                            </div>

                            {modalMode === "injection" && (
                                <div className="p-4 rounded-lg" style={{ background: "rgba(18,21,29,0.65)", border: "1px solid var(--l2-hairline)" }}>
                                    <label className="block text-xs font-medium uppercase tracking-wider mb-3" style={{ color: "var(--l2-fg-2)" }}>Divisão de Sócios</label>
                                    <div className="flex gap-2 mb-4">
                                        <button type="button" onClick={() => setSplitType("50-50")}
                                            className="flex-1 py-1.5 rounded text-sm font-medium transition-colors"
                                            style={{ background: splitType === "50-50" ? "var(--atlas-celestial)" : "rgba(34,40,56,0.65)", color: splitType === "50-50" ? "#FFF" : "var(--l2-fg-2)" }}>
                                            50/50
                                        </button>
                                        <button type="button" onClick={() => setSplitType("custom")}
                                            className="flex-1 py-1.5 rounded text-sm font-medium transition-colors"
                                            style={{ background: splitType === "custom" ? "var(--atlas-celestial)" : "rgba(34,40,56,0.65)", color: splitType === "custom" ? "#FFF" : "var(--l2-fg-2)" }}>
                                            Personalizada
                                        </button>
                                    </div>

                                    {splitType === "custom" && (
                                        <div className="flex items-center gap-4">
                                            <div className="flex-1">
                                                <label className="block text-[10px] uppercase mb-1" style={{ color: "var(--l2-fg-3)" }}>Artur (%)</label>
                                                <input type="number" min="0" max="100" value={arturPct} onChange={(e) => { setArturPct(Number(e.target.value)); setDaviPct(100 - Number(e.target.value)); }} className="input-l2 w-full px-3 py-1.5 rounded text-sm" />
                                            </div>
                                            <div className="flex-1">
                                                <label className="block text-[10px] uppercase mb-1" style={{ color: "var(--l2-fg-3)" }}>Davi (%)</label>
                                                <input type="number" min="0" max="100" value={daviPct} onChange={(e) => { setDaviPct(Number(e.target.value)); setArturPct(100 - Number(e.target.value)); }} className="input-l2 w-full px-3 py-1.5 rounded text-sm" />
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}

                            {modalMode === "withdrawal" && (
                                <div>
                                    <label className="block text-xs font-medium uppercase tracking-wider mb-2" style={{ color: "var(--l2-fg-2)" }}>Quem está sacando?</label>
                                    <div className="grid grid-cols-2 gap-3">
                                        <button type="button" onClick={() => setSelectedPartner("artur")}
                                            className="py-3 rounded-lg border transition-all"
                                            style={{
                                                borderColor: selectedPartner === "artur" ? "var(--atlas-celestial)" : "var(--l2-hairline)",
                                                background: selectedPartner === "artur" ? "rgba(79,139,255,0.1)" : "rgba(18,21,29,0.65)",
                                                color: selectedPartner === "artur" ? "var(--atlas-celestial)" : "var(--l2-fg-2)"
                                            }}>Artur</button>
                                        <button type="button" onClick={() => setSelectedPartner("davi")}
                                            className="py-3 rounded-lg border transition-all"
                                            style={{
                                                borderColor: selectedPartner === "davi" ? "var(--atlas-celestial)" : "var(--l2-hairline)",
                                                background: selectedPartner === "davi" ? "rgba(79,139,255,0.1)" : "rgba(18,21,29,0.65)",
                                                color: selectedPartner === "davi" ? "var(--atlas-celestial)" : "var(--l2-fg-2)"
                                            }}>Davi</button>
                                    </div>
                                </div>
                            )}

                            <div>
                                <label className="block text-xs font-medium uppercase tracking-wider mb-2" style={{ color: "var(--l2-fg-2)" }}>Descrição / Referência</label>
                                <input type="text" value={desc} onChange={(e) => setDesc(e.target.value)}
                                    className="input-l2 w-full px-4 py-2.5 rounded-lg" placeholder="Ex: Pagamento Nubank" />
                            </div>

                            <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
                                <button type="button" onClick={closeModal} className="flex-1 px-4 py-2.5 rounded-lg font-medium transition-colors"
                                    style={{ background: "rgba(34,40,56,0.65)", color: "var(--l2-fg-2)" }}
                                    onMouseEnter={(e) => { e.currentTarget.style.background = "var(--l2-hairline)"; }}
                                    onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(34,40,56,0.65)"; }}>
                                    Cancelar
                                </button>
                                <button type="submit" disabled={modalMode === "withdrawal" && !selectedPartner} className="flex-1 px-4 py-2.5 btn-primary rounded-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed">
                                    Confirmar
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
