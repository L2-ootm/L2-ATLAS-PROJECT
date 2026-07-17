"use client";

import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { Invoice } from "@/lib/types";
import { generateId } from "@/lib/utils";
import { getClients } from "@/app/actions";
import { Client } from "@/lib/types";

interface InvoiceModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSave: (invoice: Invoice) => void;
    invoice?: Invoice | null;
}

export default function InvoiceModal({ isOpen, onClose, onSave, invoice }: InvoiceModalProps) {
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [draftId, setDraftId] = useState("");
    const [clientId, setClientId] = useState("");
    const [description, setDescription] = useState("");
    const [amount, setAmount] = useState("");
    const [issueDate, setIssueDate] = useState("");
    const [dueDate, setDueDate] = useState("");
    const [status, setStatus] = useState<"pendente" | "pago" | "atrasado">("pendente");
    const [paidDate, setPaidDate] = useState("");
    const [clients, setClients] = useState<Client[]>([]);

    useEffect(() => {
        if (isOpen) {
            getClients().then((cls) => setClients(cls.filter((c: any) => c.active)));
        }
    }, [isOpen]);

    useEffect(() => {
        if (invoice) {
            setDraftId(invoice.id);
            setClientId(invoice.clientId);
            setDescription(invoice.description);
            setAmount(String(invoice.amount));
            setIssueDate(invoice.issueDate);
            setDueDate(invoice.dueDate);
            setStatus(invoice.status);
            setPaidDate(invoice.paidDate || "");
        } else {
            setDraftId(generateId());
            setClientId("");
            setDescription("");
            setAmount("");
            setIssueDate(new Date().toISOString().split("T")[0]);
            setDueDate("");
            setStatus("pendente");
            setPaidDate("");
        }
    }, [invoice, isOpen]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        setIsSubmitting(true);
        setTimeout(() => {
            const selectedClient = clients.find((c) => c.id === clientId);
            onSave({
                id: draftId,
                clientId,
                clientName: selectedClient?.name || "—",
                description,
                amount: parseFloat(amount) || 0,
                issueDate,
                dueDate,
                paidDate: status === "pago" ? (paidDate || new Date().toISOString().split("T")[0]) : null,
                status,
            });
            setIsSubmitting(false);
            onClose();
        }, 500);
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 transition-all" style={{ background: "rgba(0,0,0,0.5)" }} onClick={!isSubmitting ? onClose : undefined}>
            <div className="animate-l2-enter relative overflow-hidden" style={{ borderRadius: 12, padding: 32, width: "100%", maxWidth: 520, background: "rgba(24,28,38,0.55)", border: "1px solid var(--l2-hairline)", boxShadow: "0 24px 48px rgba(0,0,0,0.4)" }} onClick={(e) => e.stopPropagation()}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
                    <h2 className="text-lg font-bold" style={{ color: "var(--l2-fg-1)" }}>
                        {invoice ? "Editar Fatura" : "Nova Fatura"}
                    </h2>
                    <button onClick={onClose} className="p-1.5 rounded-lg transition-colors" style={{ color: "var(--l2-fg-3)" }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(34,40,56,0.65)"; e.currentTarget.style.color = "var(--l2-fg-1)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--l2-fg-3)"; }}>
                        <X className="w-5 h-5" />
                    </button>
                </div>
                <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                    <div>
                        <label className="block text-xs font-medium uppercase tracking-wider" style={{ marginBottom: 8, color: "var(--l2-fg-2)" }}>
                            Cliente
                        </label>
                        <select required value={clientId} onChange={(e) => setClientId(e.target.value)}
                            className="input-l2 w-full px-4 py-2.5 rounded-lg"
                            style={{ appearance: "none", cursor: "pointer" }}>
                            <option value="">Selecione um cliente</option>
                            {clients.map((c) => (
                                <option key={c.id} value={c.id}>{c.name}</option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label className="block text-xs font-medium uppercase tracking-wider" style={{ marginBottom: 8, color: "var(--l2-fg-2)" }}>
                            Descrição
                        </label>
                        <input type="text" required value={description} onChange={(e) => setDescription(e.target.value)}
                            className="input-l2 w-full px-4 py-2.5 rounded-lg"
                            placeholder="Ex: Mensalidade Fevereiro" />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs font-medium uppercase tracking-wider" style={{ marginBottom: 8, color: "var(--l2-fg-2)" }}>
                                Valor (R$)
                            </label>
                            <input type="number" required min="0" step="0.01" value={amount}
                                onChange={(e) => setAmount(e.target.value)}
                                className="input-l2 w-full px-4 py-2.5 rounded-lg font-mono" placeholder="0,00" />
                        </div>
                        <div>
                            <label className="block text-xs font-medium uppercase tracking-wider" style={{ marginBottom: 8, color: "var(--l2-fg-2)" }}>
                                Status
                            </label>
                            <select value={status} onChange={(e) => setStatus(e.target.value as typeof status)}
                                className="input-l2 w-full px-4 py-2.5 rounded-lg"
                                style={{ appearance: "none", cursor: "pointer" }}>
                                <option value="pendente">🟡 Pendente</option>
                                <option value="pago">🟢 Pago</option>
                                <option value="atrasado">🔴 Atrasado</option>
                            </select>
                        </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs font-medium uppercase tracking-wider" style={{ marginBottom: 8, color: "var(--l2-fg-2)" }}>
                                Data de Emissão
                            </label>
                            <input type="date" required value={issueDate} onChange={(e) => setIssueDate(e.target.value)}
                                className="input-l2 w-full px-4 py-2.5 rounded-lg" />
                        </div>
                        <div>
                            <label className="block text-xs font-medium uppercase tracking-wider" style={{ marginBottom: 8, color: "var(--l2-fg-2)" }}>
                                Vencimento
                            </label>
                            <input type="date" required value={dueDate} onChange={(e) => setDueDate(e.target.value)}
                                className="input-l2 w-full px-4 py-2.5 rounded-lg" />
                        </div>
                    </div>
                    {status === "pago" && (
                        <div>
                            <label className="block text-xs font-medium uppercase tracking-wider" style={{ marginBottom: 8, color: "var(--l2-fg-2)" }}>
                                Data do Pagamento
                            </label>
                            <input type="date" value={paidDate} onChange={(e) => setPaidDate(e.target.value)}
                                className="input-l2 w-full px-4 py-2.5 rounded-lg" />
                        </div>
                    )}
                    <div style={{ display: "flex", gap: 12, paddingTop: 8 }}>
                        <button type="button" onClick={onClose} disabled={isSubmitting}
                            className="flex-1 px-4 py-2.5 rounded-lg font-medium transition-colors disabled:opacity-50"
                            style={{ background: "rgba(34,40,56,0.65)", color: "var(--l2-fg-2)" }}
                            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--l2-hairline)"; }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(34,40,56,0.65)"; }}>
                            Cancelar
                        </button>
                        <button type="submit" disabled={isSubmitting} className="flex-1 px-4 py-2.5 btn-primary rounded-lg font-semibold flex justify-center items-center gap-2 transition-all disabled:opacity-80 disabled:cursor-wait">
                            {isSubmitting ? (
                                <>
                                    <span className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                                    Salvando...
                                </>
                            ) : invoice ? "Salvar" : "Criar Fatura"}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
