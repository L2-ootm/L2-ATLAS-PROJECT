"use client";

import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { Client } from "@/lib/types";
import { generateId } from "@/lib/utils";

interface ClientModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSave: (client: Client) => void;
    client?: Client | null;
}

export default function ClientModal({ isOpen, onClose, onSave, client }: ClientModalProps) {
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [draftId, setDraftId] = useState("");
    const [name, setName] = useState("");
    const [service, setService] = useState("");
    const [monthlyPayment, setMonthlyPayment] = useState("");
    const [startDate, setStartDate] = useState("");
    const [contractMonths, setContractMonths] = useState("0");
    const [active, setActive] = useState(true);
    const [notes, setNotes] = useState("");
    const [phone, setPhone] = useState("");

    useEffect(() => {
        if (client) {
            setDraftId(client.id);
            setName(client.name); setService(client.service);
            setMonthlyPayment(String(client.monthlyPayment)); setStartDate(client.startDate);
            setContractMonths(String(client.contractMonths || 0));
            setActive(client.active); setNotes(client.notes || "");
            setPhone(client.phone || "");
        } else {
            setDraftId(generateId());
            setName(""); setService(""); setMonthlyPayment("");
            setStartDate(new Date().toISOString().split("T")[0]);
            setContractMonths("0");
            setActive(true); setNotes(""); setPhone("");
        }
    }, [client, isOpen]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        setIsSubmitting(true);
        setTimeout(() => {
            onSave({ id: draftId, name, service, monthlyPayment: parseFloat(monthlyPayment) || 0, startDate, contractMonths: parseInt(contractMonths) || 0, active, notes, phone });
            setIsSubmitting(false);
            onClose();
        }, 500);
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 transition-all" style={{ background: "rgba(0,0,0,0.5)" }} onClick={!isSubmitting ? onClose : undefined}>
            <div className="animate-l2-enter relative overflow-hidden" style={{ borderRadius: 12, padding: 32, width: "100%", maxWidth: 520, background: "rgba(24,28,38,0.55)", border: "1px solid var(--l2-hairline)", boxShadow: "0 24px 48px rgba(0,0,0,0.4)" }} onClick={(e) => e.stopPropagation()}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
                    <h2 className="text-lg font-bold" style={{ color: "var(--l2-fg-1)" }}>{client ? "Editar Cliente" : "Novo Cliente"}</h2>
                    <button onClick={onClose} className="p-1.5 rounded-lg transition-colors" style={{ color: "var(--l2-fg-3)" }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(34,40,56,0.65)"; e.currentTarget.style.color = "var(--l2-fg-1)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--l2-fg-3)"; }}>
                        <X className="w-5 h-5" />
                    </button>
                </div>
                <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                    <div>
                        <label className="block text-xs font-medium uppercase tracking-wider" style={{ marginBottom: 8, color: "var(--l2-fg-2)" }}>Nome do Cliente</label>
                        <input type="text" required value={name} onChange={(e) => setName(e.target.value)}
                            className="input-l2 w-full px-4 py-2.5 rounded-lg" placeholder="Ex: Clínica Dr. Silva" />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs font-medium uppercase tracking-wider" style={{ marginBottom: 8, color: "var(--l2-fg-2)" }}>Serviço Prestado</label>
                            <input type="text" required value={service} onChange={(e) => setService(e.target.value)}
                                className="input-l2 w-full px-4 py-2.5 rounded-lg" placeholder="Ex: Gestão de WhatsApp" />
                        </div>
                        <div>
                            <label className="block text-xs font-medium uppercase tracking-wider" style={{ marginBottom: 8, color: "var(--l2-fg-2)" }}>WhatsApp (Cobrança)</label>
                            <input type="text" value={phone} onChange={(e) => setPhone(e.target.value)}
                                className="input-l2 w-full px-4 py-2.5 rounded-lg" placeholder="Ex: 5511999999999" />
                        </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs font-medium uppercase tracking-wider" style={{ marginBottom: 8, color: "var(--l2-fg-2)" }}>Valor Mensal (R$)</label>
                            <input type="number" required min="0" step="0.01" value={monthlyPayment} onChange={(e) => setMonthlyPayment(e.target.value)}
                                className="input-l2 w-full px-4 py-2.5 rounded-lg font-mono" placeholder="0,00" />
                        </div>
                        <div>
                            <label className="block text-xs font-medium uppercase tracking-wider" style={{ marginBottom: 8, color: "var(--l2-fg-2)" }}>Início do Contrato</label>
                            <input type="date" required value={startDate} onChange={(e) => setStartDate(e.target.value)}
                                className="input-l2 w-full px-4 py-2.5 rounded-lg" />
                        </div>
                    </div>
                    <div>
                        <label className="block text-xs font-medium uppercase tracking-wider" style={{ marginBottom: 8, color: "var(--l2-fg-2)" }}>Vigência do Contrato (Meses)</label>
                        <select value={contractMonths} onChange={(e) => setContractMonths(e.target.value)} className="input-l2 w-full px-4 py-2.5 rounded-lg text-sm" style={{ background: "rgba(18,21,29,0.65)" }}>
                            <option value="0">Sem Fidelidade (Recorrente Mensal)</option>
                            <option value="3">3 Meses (Trimestral)</option>
                            <option value="6">6 Meses (Semestral)</option>
                            <option value="12">12 Meses (Anual)</option>
                            <option value="24">24 Meses (Bianual)</option>
                        </select>
                    </div>
                    <div className="flex items-center gap-3">
                        <label className="relative inline-flex items-center cursor-pointer">
                            <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} className="sr-only peer" />
                            <div className="w-10 h-5 rounded-full peer after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-full" style={{ background: active ? "#4F8BFF" : "rgba(34,40,56,0.65)" }}><div className="absolute top-[2px] rounded-full h-4 w-4 bg-white transition-all" style={{ left: active ? "22px" : "2px" }} /></div>
                        </label>
                        <span className="text-sm" style={{ color: "var(--l2-fg-2)" }}>Cliente ativo</span>
                    </div>
                    <div>
                        <label className="block text-xs font-medium uppercase tracking-wider" style={{ marginBottom: 8, color: "var(--l2-fg-2)" }}>Observações</label>
                        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3}
                            className="input-l2 w-full px-4 py-2.5 rounded-lg resize-none" placeholder="Notas opcionais..." />
                    </div>
                    <div style={{ display: "flex", gap: 12, paddingTop: 8 }}>
                        <button type="button" onClick={onClose} disabled={isSubmitting} className="flex-1 px-4 py-2.5 rounded-lg font-medium transition-colors disabled:opacity-50"
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
                            ) : client ? "Salvar" : "Adicionar"}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
