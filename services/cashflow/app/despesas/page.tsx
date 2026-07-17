"use client";

import { useState, useEffect, useMemo } from "react";
import { Plus, Receipt, TrendingDown, Repeat, Edit2, Trash2 } from "lucide-react";
import StatCard from "@/components/StatCard";
import MonthSelector from "@/components/MonthSelector";
import ExpenseModal from "@/components/ExpenseModal";
import { getExpenses, addExpense, updateExpense, deleteExpense, getClients } from "@/app/actions";
import { formatCurrency, formatDate, getMonthYear } from "@/lib/utils";
import { Expense, Client, EXPENSE_CATEGORIES } from "@/lib/types";

export default function DespesasPage() {
    const [expenses, setExpenses] = useState<Expense[]>([]);
    const [clients, setClients] = useState<Client[]>([]);
    const [month, setMonth] = useState(() => getMonthYear(new Date()));
    const [modalOpen, setModalOpen] = useState(false);
    const [editExpense, setEditExpense] = useState<Expense | null>(null);
    const [filterCat, setFilterCat] = useState<string>("all");

    useEffect(() => {
        refresh();
    }, []);

    const refresh = async () => {
        setExpenses(await getExpenses());
        setClients(await getClients());
    };

    const monthExpenses = useMemo(() => expenses.filter((e) => e.date.startsWith(month)), [expenses, month]);

    const filtered = useMemo(() => {
        let list = monthExpenses;
        if (filterCat !== "all") list = list.filter((e) => e.category === filterCat);
        return list.sort((a, b) => b.date.localeCompare(a.date));
    }, [monthExpenses, filterCat]);

    const total = useMemo(() => monthExpenses.reduce((s, e) => s + e.amount, 0), [monthExpenses]);
    const recurring = useMemo(() => monthExpenses.filter((e) => e.recurring).reduce((s, e) => s + e.amount, 0), [monthExpenses]);

    const getClientName = (id: string | null) => !id ? "L2 Geral" : clients.find((c) => c.id === id)?.name || "—";

    const handleSave = async (expense: Expense) => {
        if (editExpense) { await updateExpense(expense); } else { await addExpense(expense); }
        await refresh();
        setEditExpense(null);
    };

    const handleDelete = async (id: string) => {
        await deleteExpense(id);
        await refresh();
    };

    const catBadge = (cat: string) => {
        const cls = `cat-${cat.toLowerCase()}`;
        return (
            <span className={cls} style={{ display: "inline-block", padding: "4px 10px", borderRadius: 6, fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                {cat}
            </span>
        );
    };

    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
            {/* Header */}
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
                <div>
                    <h1 className="text-2xl font-bold" style={{ color: "var(--l2-fg-1)" }}>Despesas</h1>
                    <p className="text-sm mt-0.5" style={{ color: "var(--l2-fg-3)" }}>Controle de custos e despesas operacionais</p>
                </div>
                <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                    <MonthSelector value={month} onChange={setMonth} />
                    <button
                        onClick={() => { setEditExpense(null); setModalOpen(true); }}
                        style={{
                            display: "flex", alignItems: "center", gap: 8,
                            padding: "10px 24px", borderRadius: 8,
                            background: "rgba(79,139,255,0.14)", color: "var(--atlas-celestial-soft)", fontWeight: 600, fontSize: 14,
                            border: "1px solid rgba(79,139,255,0.38)", cursor: "pointer",
                            boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                            transition: "background 200ms",
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(79,139,255,0.24)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(79,139,255,0.14)"; }}
                    >
                        <Plus style={{ width: 18, height: 18 }} />
                        Nova Despesa
                    </button>
                </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <StatCard title="Total do Mês" value={formatCurrency(total)} icon={TrendingDown} accentColor="red" />
                <StatCard title="Recorrentes" value={formatCurrency(recurring)} icon={Repeat} accentColor="yellow" />
                <StatCard title="Qtd. Registros" value={String(monthExpenses.length)} icon={Receipt} accentColor="cyan" />
            </div>

            {/* Category Filters */}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button onClick={() => setFilterCat("all")}
                    style={{
                        padding: "8px 16px", borderRadius: 8, fontSize: 13, fontWeight: 500,
                        background: filterCat === "all" ? "rgba(79,139,255,0.12)" : "transparent",
                        color: filterCat === "all" ? "var(--atlas-celestial)" : "var(--l2-fg-2)",
                        border: filterCat === "all" ? "1px solid rgba(79,139,255,0.25)" : "1px solid var(--l2-hairline)",
                        cursor: "pointer", transition: "all 200ms",
                    }}>
                    Todas
                </button>
                {EXPENSE_CATEGORIES.map((cat) => (
                    <button key={cat} onClick={() => setFilterCat(cat)}
                        style={{
                            padding: "8px 16px", borderRadius: 8, fontSize: 13, fontWeight: 500,
                            background: filterCat === cat ? "rgba(79,139,255,0.12)" : "transparent",
                            color: filterCat === cat ? "var(--atlas-celestial)" : "var(--l2-fg-2)",
                            border: filterCat === cat ? "1px solid rgba(79,139,255,0.25)" : "1px solid var(--l2-hairline)",
                            cursor: "pointer", transition: "all 200ms",
                        }}>
                        {cat}
                    </button>
                ))}
            </div>

            {/* Table */}
            <div className="l2-border" style={{ borderRadius: 12, overflow: "hidden", background: "rgba(24,28,38,0.55)" }}>
                <div style={{
                    display: "grid",
                    gridTemplateColumns: "2fr 1.5fr 1fr 1fr 1fr 80px",
                    padding: "14px 24px",
                    borderBottom: "1px solid var(--l2-hairline)",
                    background: "rgba(18,21,29,0.65)",
                }}>
                    <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: "var(--l2-fg-3)" }}>Descrição</span>
                    <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: "var(--l2-fg-3)" }}>Cliente</span>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-center" style={{ color: "var(--l2-fg-3)" }}>Categoria</span>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-right" style={{ color: "var(--l2-fg-3)" }}>Valor</span>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-center" style={{ color: "var(--l2-fg-3)" }}>Data</span>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-center" style={{ color: "var(--l2-fg-3)" }}>Ações</span>
                </div>

                {filtered.length === 0 ? (
                    <div style={{ padding: "48px 24px", textAlign: "center" }}>
                        <p className="text-sm" style={{ color: "var(--l2-fg-3)" }}>Nenhuma despesa encontrada</p>
                    </div>
                ) : (
                    filtered.map((exp, i) => (
                        <div key={exp.id} style={{
                            display: "grid",
                            gridTemplateColumns: "2fr 1.5fr 1fr 1fr 1fr 80px",
                            padding: "16px 24px",
                            alignItems: "center",
                            borderBottom: i < filtered.length - 1 ? "1px solid rgba(34,40,56,0.65)" : "none",
                            transition: "background 150ms",
                        }}
                            onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(18,21,29,0.65)"; }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                        >
                            <div>
                                <span className="text-sm truncate block" style={{ color: "var(--l2-fg-1)" }}>{exp.description}</span>
                                {exp.recurring && <span className="text-[9px] font-mono uppercase mt-0.5 flex items-center gap-1" style={{ color: "var(--sig-amber)" }}><Repeat className="w-3 h-3" /> Recorrente</span>}
                            </div>
                            <span className="text-sm truncate" style={{ color: "var(--l2-fg-2)" }}>{getClientName(exp.clientId)}</span>
                            <div className="text-center">{catBadge(exp.category)}</div>
                            <span className="text-sm font-mono font-semibold text-right" style={{ color: "var(--sig-crimson)" }}>{formatCurrency(exp.amount)}</span>
                            <span className="text-sm font-mono text-center" style={{ color: "var(--l2-fg-2)" }}>{formatDate(exp.date)}</span>
                            <div style={{ display: "flex", gap: 4, justifyContent: "center" }}>
                                <button onClick={() => { setEditExpense(exp); setModalOpen(true); }}
                                    title="Editar"
                                    className="p-2 rounded-lg transition-colors"
                                    style={{ color: "var(--l2-fg-3)", background: "transparent", border: "none", cursor: "pointer" }}
                                    onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(34,40,56,0.65)"; e.currentTarget.style.color = "var(--l2-fg-1)"; }}
                                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--l2-fg-3)"; }}>
                                    <Edit2 className="w-4 h-4" />
                                </button>
                                <button onClick={() => handleDelete(exp.id)}
                                    title="Excluir"
                                    className="p-2 rounded-lg transition-colors"
                                    style={{ color: "var(--l2-fg-3)", background: "transparent", border: "none", cursor: "pointer" }}
                                    onMouseEnter={(e) => { e.currentTarget.style.color = "var(--sig-crimson)"; e.currentTarget.style.background = "rgba(34,40,56,0.65)"; }}
                                    onMouseLeave={(e) => { e.currentTarget.style.color = "var(--l2-fg-3)"; e.currentTarget.style.background = "transparent"; }}>
                                    <Trash2 className="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                    ))
                )}
            </div>

            <ExpenseModal
                isOpen={modalOpen}
                onClose={() => { setModalOpen(false); setEditExpense(null); }}
                onSave={handleSave}
                expense={editExpense}
            />
        </div>
    );
}
