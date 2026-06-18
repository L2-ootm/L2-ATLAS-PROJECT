"use client";

import { useState, useEffect, useMemo } from "react";
import { FileText, DollarSign, Clock, AlertTriangle, Plus, CheckCircle2, Trash2, Edit3, MessageCircle } from "lucide-react";
import StatCard from "@/components/StatCard";
import InvoiceModal from "@/components/InvoiceModal";
import { getInvoices, addInvoice, updateInvoice, deleteInvoice, getClients } from "@/app/actions";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Invoice, Client } from "@/lib/types";

export default function FaturasPage() {
    const [invoices, setInvoices] = useState<Invoice[]>([]);
    const [modalOpen, setModalOpen] = useState(false);
    const [editInvoice, setEditInvoice] = useState<Invoice | null>(null);
    const [filterStatus, setFilterStatus] = useState<string>("all");
    const [clients, setClients] = useState<Client[]>([]);

    useEffect(() => {
        refreshInvoices();
    }, []);

    const refreshInvoices = async () => {
        const all = await getInvoices();
        setClients(await getClients());

        const today = new Date().toISOString().split("T")[0];
        let hasChanges = false;

        const updated = await Promise.all(all.map(async (inv) => {
            if (inv.status === "pendente" && inv.dueDate < today) {
                hasChanges = true;
                const upd = { ...inv, status: "atrasado" as const };
                await updateInvoice(upd);
                return upd;
            }
            return inv;
        }));

        if (hasChanges) {
            setInvoices(await getInvoices());
        } else {
            setInvoices(updated);
        }
    };

    const filtered = useMemo(() => {
        if (filterStatus === "all") return invoices;
        return invoices.filter((i) => i.status === filterStatus);
    }, [invoices, filterStatus]);

    const sorted = useMemo(() =>
        [...filtered].sort((a, b) => b.dueDate.localeCompare(a.dueDate)),
        [filtered]
    );

    const totalPending = useMemo(() =>
        invoices.filter((i) => i.status === "pendente").reduce((s, i) => s + i.amount, 0),
        [invoices]
    );
    const totalPaid = useMemo(() =>
        invoices.filter((i) => i.status === "pago").reduce((s, i) => s + i.amount, 0),
        [invoices]
    );
    const totalOverdue = useMemo(() =>
        invoices.filter((i) => i.status === "atrasado").reduce((s, i) => s + i.amount, 0),
        [invoices]
    );
    const overdueCount = useMemo(() =>
        invoices.filter((i) => i.status === "atrasado").length,
        [invoices]
    );

    const handleSave = async (invoice: Invoice) => {
        if (editInvoice) {
            await updateInvoice(invoice);
        } else {
            await addInvoice(invoice);
        }
        await refreshInvoices();
        setEditInvoice(null);
    };

    const handleDelete = async (id: string) => {
        await deleteInvoice(id);
        await refreshInvoices();
    };

    const handleMarkPaid = async (inv: Invoice) => {
        await updateInvoice({
            ...inv,
            status: "pago",
            paidDate: new Date().toISOString().split("T")[0],
        });
        await refreshInvoices();
    };

    const getClientPhone = (clientId: string) => {
        const client = clients.find(c => c.id === clientId);
        return client?.phone;
    };

    const handleWhatsApp = (inv: Invoice) => {
        const phone = getClientPhone(inv.clientId);
        if (!phone) return;

        const cleanPhone = phone.replace(/\D/g, '');
        const isAtrasado = inv.status === 'atrasado';

        const message = isAtrasado
            ? `Olá, ${inv.clientName}! Tudo bem? Aqui é o financeiro da L2. Verificamos que o boleto referente a ${inv.description}, com vencimento original em ${formatDate(inv.dueDate)}, encontra-se em aberto. Qualquer dúvida, estamos à disposição!`
            : `Olá, ${inv.clientName}! Tudo bem? Aqui é o financeiro da L2. Passando para lembrar do seu boleto referente a ${inv.description} que vence no dia ${formatDate(inv.dueDate)}. O valor é de ${formatCurrency(inv.amount)}. Qualquer dúvida, estamos à disposição!`;

        const url = `https://wa.me/${cleanPhone}?text=${encodeURIComponent(message)}`;
        window.open(url, '_blank');
    };

    const statusBadge = (status: string) => {
        const styles: Record<string, { bg: string; color: string; label: string }> = {
            pago: { bg: "rgba(52,211,153,0.1)", color: "#34D399", label: "Pago" },
            pendente: { bg: "rgba(251,191,36,0.1)", color: "#FBBF24", label: "Pendente" },
            atrasado: { bg: "rgba(248,113,113,0.1)", color: "#F87171", label: "Atrasado" },
        };
        const s = styles[status] || styles.pendente;
        return (
            <span style={{
                display: "inline-block", padding: "4px 12px", borderRadius: 6,
                fontSize: 11, fontWeight: 600, letterSpacing: "0.05em",
                textTransform: "uppercase", background: s.bg, color: s.color,
            }}>
                {s.label}
            </span>
        );
    };

    const filterButtons = [
        { key: "all", label: "Todas" },
        { key: "pendente", label: "Pendentes" },
        { key: "pago", label: "Pagas" },
        { key: "atrasado", label: "Atrasadas" },
    ];

    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
            {/* Header */}
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
                <div>
                    <h1 className="text-2xl font-bold" style={{ color: "#F1F3F6" }}>Faturas</h1>
                    <p className="text-sm mt-0.5" style={{ color: "#5C6478" }}>Gerenciamento de cobranças e pagamentos</p>
                </div>
                <button
                    onClick={() => { setEditInvoice(null); setModalOpen(true); }}
                    style={{
                        display: "flex", alignItems: "center", gap: 8,
                        padding: "10px 24px", borderRadius: 8,
                        background: "#6366F1", color: "#fff", fontWeight: 600, fontSize: 14,
                        border: "none", cursor: "pointer",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                        transition: "background 200ms",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "#818CF8"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "#6366F1"; }}
                >
                    <Plus style={{ width: 18, height: 18 }} />
                    Nova Fatura
                </button>
            </div>

            {/* Stat Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard title="Total Pendente" value={formatCurrency(totalPending)} icon={Clock} accentColor="yellow" />
                <StatCard title="Total Recebido" value={formatCurrency(totalPaid)} icon={DollarSign} accentColor="cyan" />
                <StatCard title="Total Atrasado" value={formatCurrency(totalOverdue)} icon={AlertTriangle} accentColor="red"
                    trend={overdueCount > 0 ? { value: `${overdueCount} fatura${overdueCount > 1 ? "s" : ""}`, positive: false } : undefined} />
                <StatCard title="Total Faturas" value={String(invoices.length)} icon={FileText} accentColor="violet" />
            </div>

            {/* Filter buttons */}
            <div style={{ display: "flex", gap: 8 }}>
                {filterButtons.map((f) => (
                    <button key={f.key}
                        onClick={() => setFilterStatus(f.key)}
                        style={{
                            padding: "8px 20px", borderRadius: 8, fontSize: 13, fontWeight: 500,
                            background: filterStatus === f.key ? "rgba(99,102,241,0.12)" : "transparent",
                            color: filterStatus === f.key ? "#6366F1" : "#9CA3B4",
                            border: filterStatus === f.key ? "1px solid rgba(99,102,241,0.25)" : "1px solid #2E3340",
                            cursor: "pointer",
                            transition: "all 200ms",
                        }}
                        onMouseEnter={(e) => {
                            if (filterStatus !== f.key) { e.currentTarget.style.background = "#1F2230"; e.currentTarget.style.color = "#F1F3F6"; }
                        }}
                        onMouseLeave={(e) => {
                            if (filterStatus !== f.key) { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "#9CA3B4"; }
                        }}
                    >
                        {f.label}
                    </button>
                ))}
            </div>

            {/* Invoice table */}
            <div className="l2-border" style={{ borderRadius: 12, overflow: "hidden", background: "#1A1D26" }}>
                {/* Table header */}
                <div style={{
                    display: "grid",
                    gridTemplateColumns: "2fr 1.5fr 1fr 1fr 1fr 120px",
                    padding: "14px 24px",
                    borderBottom: "1px solid #2E3340",
                    background: "#1F2230",
                }}>
                    <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: "#5C6478" }}>Cliente</span>
                    <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: "#5C6478" }}>Descrição</span>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-right" style={{ color: "#5C6478" }}>Valor</span>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-center" style={{ color: "#5C6478" }}>Vencimento</span>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-center" style={{ color: "#5C6478" }}>Status</span>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-center" style={{ color: "#5C6478" }}>Ações</span>
                </div>

                {sorted.length === 0 ? (
                    <div style={{ padding: "48px 24px", textAlign: "center" }}>
                        <p className="text-sm" style={{ color: "#5C6478" }}>Nenhuma fatura encontrada</p>
                    </div>
                ) : (
                    sorted.map((inv, i) => (
                        <div key={inv.id} style={{
                            display: "grid",
                            gridTemplateColumns: "2fr 1.5fr 1fr 1fr 1fr 120px",
                            padding: "16px 24px",
                            alignItems: "center",
                            borderBottom: i < sorted.length - 1 ? "1px solid #252937" : "none",
                            transition: "background 150ms",
                        }}
                            onMouseEnter={(e) => { e.currentTarget.style.background = "#1F2230"; }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                        >
                            <span className="text-sm font-medium truncate" style={{ color: "#F1F3F6" }}>{inv.clientName}</span>
                            <span className="text-sm truncate" style={{ color: "#9CA3B4" }}>{inv.description}</span>
                            <span className="text-sm font-mono font-semibold text-right" style={{ color: "#F1F3F6" }}>{formatCurrency(inv.amount)}</span>
                            <span className="text-sm font-mono text-center" style={{ color: "#9CA3B4" }}>{formatDate(inv.dueDate)}</span>
                            <div style={{ textAlign: "center" }}>{statusBadge(inv.status)}</div>
                            <div style={{ display: "flex", gap: 6, justifyContent: "center" }}>
                                {inv.status !== "pago" && getClientPhone(inv.clientId) && (
                                    <button onClick={() => handleWhatsApp(inv)}
                                        title="Cobrar via WhatsApp"
                                        style={{
                                            padding: 6, borderRadius: 6, background: "rgba(37,211,102,0.1)",
                                            border: "none", cursor: "pointer", color: "#25D366",
                                            transition: "all 200ms",
                                        }}
                                        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(37,211,102,0.2)"; }}
                                        onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(37,211,102,0.1)"; }}
                                    >
                                        <MessageCircle style={{ width: 16, height: 16 }} />
                                    </button>
                                )}
                                {inv.status !== "pago" && (
                                    <button onClick={() => handleMarkPaid(inv)}
                                        title="Marcar como pago"
                                        style={{
                                            padding: 6, borderRadius: 6, background: "rgba(52,211,153,0.1)",
                                            border: "none", cursor: "pointer", color: "#34D399",
                                            transition: "all 200ms",
                                        }}
                                        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(52,211,153,0.2)"; }}
                                        onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(52,211,153,0.1)"; }}
                                    >
                                        <CheckCircle2 style={{ width: 16, height: 16 }} />
                                    </button>
                                )}
                                <button onClick={() => { setEditInvoice(inv); setModalOpen(true); }}
                                    title="Editar"
                                    style={{
                                        padding: 6, borderRadius: 6, background: "rgba(99,102,241,0.1)",
                                        border: "none", cursor: "pointer", color: "#6366F1",
                                        transition: "all 200ms",
                                    }}
                                    onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(99,102,241,0.2)"; }}
                                    onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(99,102,241,0.1)"; }}
                                >
                                    <Edit3 style={{ width: 16, height: 16 }} />
                                </button>
                                <button onClick={() => handleDelete(inv.id)}
                                    title="Excluir"
                                    style={{
                                        padding: 6, borderRadius: 6, background: "rgba(248,113,113,0.1)",
                                        border: "none", cursor: "pointer", color: "#F87171",
                                        transition: "all 200ms",
                                    }}
                                    onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(248,113,113,0.2)"; }}
                                    onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(248,113,113,0.1)"; }}
                                >
                                    <Trash2 style={{ width: 16, height: 16 }} />
                                </button>
                            </div>
                        </div>
                    ))
                )}
            </div>

            <InvoiceModal
                isOpen={modalOpen}
                onClose={() => { setModalOpen(false); setEditInvoice(null); }}
                onSave={handleSave}
                invoice={editInvoice}
            />
        </div>
    );
}
