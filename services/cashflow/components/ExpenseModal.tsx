"use client";

import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { Expense, EXPENSE_CATEGORIES, ExpenseCategory } from "@/lib/types";
import { generateId } from "@/lib/utils";
import { getClients } from "@/app/actions";

interface ExpenseModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSave: (expense: Expense) => void;
    expense?: Expense | null;
}

export default function ExpenseModal({ isOpen, onClose, onSave, expense }: ExpenseModalProps) {
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [draftId, setDraftId] = useState("");
    const [clientId, setClientId] = useState<string>("null");
    const [category, setCategory] = useState<ExpenseCategory>("Outros");
    const [description, setDescription] = useState("");
    const [amount, setAmount] = useState("");
    const [date, setDate] = useState("");
    const [recurring, setRecurring] = useState(false);
    const [clients, setClients] = useState<{ id: string; name: string }[]>([]);

    useEffect(() => {
        if (isOpen) {
            getClients().then((cls) => setClients(cls.map((c: any) => ({ id: c.id, name: c.name }))));
        }
    }, [isOpen]);

    useEffect(() => {
        if (expense) {
            setDraftId(expense.id);
            setClientId(expense.clientId || "null"); setCategory(expense.category);
            setDescription(expense.description); setAmount(String(expense.amount));
            setDate(expense.date); setRecurring(expense.recurring);
        } else {
            setDraftId(generateId());
            setClientId("null"); setCategory("Outros"); setDescription(""); setAmount("");
            setDate(new Date().toISOString().split("T")[0]); setRecurring(false);
        }
    }, [expense, isOpen]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        setIsSubmitting(true);
        setTimeout(() => {
            onSave({ id: draftId, clientId: clientId === "null" ? null : clientId, category, description, amount: parseFloat(amount) || 0, date, recurring });
            setIsSubmitting(false);
            onClose();
        }, 500);
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 transition-all" style={{ background: "rgba(0,0,0,0.5)" }} onClick={!isSubmitting ? onClose : undefined}>
            <div className="animate-l2-enter relative overflow-hidden" style={{ borderRadius: 12, padding: 24, width: "100%", maxWidth: 520, background: "#1A1D26", border: "1px solid #2E3340", boxShadow: "0 24px 48px rgba(0,0,0,0.4)" }} onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-lg font-bold" style={{ color: "#F1F3F6" }}>{expense ? "Editar Despesa" : "Nova Despesa"}</h2>
                    <button onClick={onClose} className="p-1.5 rounded-lg transition-colors" style={{ color: "#5C6478" }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = "#252937"; e.currentTarget.style.color = "#F1F3F6"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "#5C6478"; }}>
                        <X className="w-5 h-5" />
                    </button>
                </div>
                <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                    <div>
                        <label className="block text-xs mb-2 font-medium uppercase tracking-wider" style={{ color: "#9CA3B4" }}>Descrição</label>
                        <input type="text" required value={description} onChange={(e) => setDescription(e.target.value)}
                            className="input-l2 w-full px-4 py-2.5 rounded-lg" placeholder="Ex: Assinatura OpenAI" />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs mb-2 font-medium uppercase tracking-wider" style={{ color: "#9CA3B4" }}>Valor (R$)</label>
                            <input type="number" required min="0" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)}
                                className="input-l2 w-full px-4 py-2.5 rounded-lg font-mono" placeholder="0,00" />
                        </div>
                        <div>
                            <label className="block text-xs mb-2 font-medium uppercase tracking-wider" style={{ color: "#9CA3B4" }}>Data</label>
                            <input type="date" required value={date} onChange={(e) => setDate(e.target.value)}
                                className="input-l2 w-full px-4 py-2.5 rounded-lg" />
                        </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs mb-2 font-medium uppercase tracking-wider" style={{ color: "#9CA3B4" }}>Categoria</label>
                            <select value={category} onChange={(e) => setCategory(e.target.value as ExpenseCategory)}
                                className="input-l2 w-full px-4 py-2.5 rounded-lg" style={{ background: "#1F2230" }}>
                                {EXPENSE_CATEGORIES.map((cat) => (<option key={cat} value={cat}>{cat}</option>))}
                            </select>
                        </div>
                        <div>
                            <label className="block text-xs mb-2 font-medium uppercase tracking-wider" style={{ color: "#9CA3B4" }}>Cliente</label>
                            <select value={clientId} onChange={(e) => setClientId(e.target.value)}
                                className="input-l2 w-full px-4 py-2.5 rounded-lg" style={{ background: "#1F2230" }}>
                                <option value="null">L2 Geral</option>
                                {clients.map((c) => (<option key={c.id} value={c.id}>{c.name}</option>))}
                            </select>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <label className="relative inline-flex items-center cursor-pointer">
                            <input type="checkbox" checked={recurring} onChange={(e) => setRecurring(e.target.checked)} className="sr-only peer" />
                            <div className="w-10 h-5 rounded-full peer after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-full" style={{ background: recurring ? "#6366F1" : "#252937" }}><div className="absolute top-[2px] rounded-full h-4 w-4 bg-white transition-all" style={{ left: recurring ? "22px" : "2px" }} /></div>
                        </label>
                        <span className="text-sm" style={{ color: "#9CA3B4" }}>Despesa recorrente</span>
                    </div>
                    <div style={{ display: "flex", gap: 12, paddingTop: 8 }}>
                        <button type="button" onClick={onClose} disabled={isSubmitting} className="flex-1 px-4 py-2.5 rounded-lg font-medium transition-colors disabled:opacity-50"
                            style={{ background: "#252937", color: "#9CA3B4" }}
                            onMouseEnter={(e) => { e.currentTarget.style.background = "#2E3340"; }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = "#252937"; }}>
                            Cancelar
                        </button>
                        <button type="submit" disabled={isSubmitting} className="flex-1 px-4 py-2.5 btn-primary rounded-lg font-semibold flex justify-center items-center gap-2 transition-all disabled:opacity-80 disabled:cursor-wait">
                            {isSubmitting ? (
                                <>
                                    <span className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                                    Registrando...
                                </>
                            ) : expense ? "Salvar" : "Adicionar"}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
