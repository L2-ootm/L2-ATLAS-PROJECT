"use client";

import { useState, useEffect } from "react";
import { Search, Plus, FileText, UserPlus, X, Wallet, Command } from "lucide-react";
import { useRouter } from "next/navigation";
import ExpenseModal from "./ExpenseModal";
import InvoiceModal from "./InvoiceModal";
import ClientModal from "./ClientModal";

export default function NeuralCommandOverlay() {
    const [open, setOpen] = useState(false);
    const [search, setSearch] = useState("");
    const router = useRouter();

    // Modal states invoked from command palette
    const [showExpense, setShowExpense] = useState(false);
    const [showInvoice, setShowInvoice] = useState(false);
    const [showClient, setShowClient] = useState(false);

    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.ctrlKey || e.metaKey) && e.key === "k") {
                e.preventDefault();
                setOpen(p => !p);
            }
            if (e.key === "Escape") setOpen(false);
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, []);

    if (!open && !showExpense && !showInvoice && !showClient) return null;

    const commands = [
        { id: "add_expense", label: "Adicionar Nova Despesa", icon: Plus, color: "text-red-400", action: () => { setOpen(false); setShowExpense(true); } },
        { id: "add_invoice", label: "Emitir Fatura", icon: FileText, color: "text-[var(--atlas-cyan)]", action: () => { setOpen(false); setShowInvoice(true); } },
        { id: "add_client", label: "Cadastrar Cliente", icon: UserPlus, color: "text-indigo-400", action: () => { setOpen(false); setShowClient(true); } },
        { id: "goto_dashboard", label: "Ir para Dashboard", icon: Command, color: "text-blue-400", action: () => { setOpen(false); router.push("/dashboard"); } },
        { id: "goto_reports", label: "Abrir Relatórios", icon: Wallet, color: "text-slate-300", action: () => { setOpen(false); router.push("/relatorios"); } },
    ];

    const filtered = commands.filter(c => c.label.toLowerCase().includes(search.toLowerCase()));

    return (
        <>
            {/* Global Overlay for Command Palette */}
            {open && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.5)" }}>
                    <div className="absolute inset-0" onClick={() => setOpen(false)} />

                    <div className="relative w-full max-w-2xl overflow-hidden flex flex-col animate-l2-enter"
                        style={{ background: "rgba(24,28,38,0.55)", border: "1px solid var(--l2-hairline)", borderRadius: 12, boxShadow: "0 24px 48px rgba(0,0,0,0.4)" }}>
                        {/* Header / Input */}
                        <div className="flex items-center px-4 py-3" style={{ borderBottom: "1px solid var(--l2-hairline)" }}>
                            <Search className="w-5 h-5 mr-3" style={{ color: "var(--l2-fg-3)" }} />
                            <input
                                autoFocus
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                placeholder="O que você precisa fazer?"
                                className="flex-1 bg-transparent outline-none text-lg"
                                style={{ color: "var(--l2-fg-1)" }}
                            />
                            <button onClick={() => setOpen(false)} className="p-1 rounded-md transition-colors" style={{ color: "var(--l2-fg-3)" }}
                                onMouseEnter={(e) => { e.currentTarget.style.color = "var(--l2-fg-1)"; e.currentTarget.style.background = "rgba(34,40,56,0.65)"; }}
                                onMouseLeave={(e) => { e.currentTarget.style.color = "var(--l2-fg-3)"; e.currentTarget.style.background = "transparent"; }}>
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        {/* Command List */}
                        <div className="p-2 max-h-[60vh] overflow-y-auto">
                            {filtered.length === 0 ? (
                                <p className="text-center text-sm py-8" style={{ color: "var(--l2-fg-3)" }}>Nenhum comando encontrado para &quot;{search}&quot;</p>
                            ) : (
                                <div className="space-y-1">
                                    <h4 className="px-3 py-2 text-[10px] uppercase tracking-wider font-bold" style={{ color: "var(--l2-fg-3)" }}>Ações Rápidas</h4>
                                    {filtered.map((cmd) => (
                                        <button
                                            key={cmd.id}
                                            onClick={cmd.action}
                                            className="w-full flex items-center gap-3 px-3 py-3 rounded-lg transition-colors text-left group"
                                            style={{ color: "var(--l2-fg-2)" }}
                                            onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(34,40,56,0.65)"; }}
                                            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                                        >
                                            <div className="p-2 rounded-lg" style={{ background: "rgba(34,40,56,0.65)", border: "1px solid var(--l2-hairline)" }}>
                                                <cmd.icon className={`w-4 h-4 ${cmd.color}`} />
                                            </div>
                                            <span className="text-sm font-medium" style={{ color: "var(--l2-fg-2)" }}>
                                                {cmd.label}
                                            </span>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Footer Hints */}
                        <div className="px-4 py-3 flex items-center justify-between" style={{ borderTop: "1px solid var(--l2-hairline)", background: "var(--l2-void-surface)" }}>
                            <span className="text-[10px]" style={{ color: "var(--l2-fg-3)" }}>Ações rápidas</span>
                            <div className="flex items-center gap-2">
                                <kbd className="text-[10px] px-1.5 py-0.5 rounded font-mono" style={{ background: "rgba(34,40,56,0.65)", border: "1px solid var(--l2-hairline)", color: "var(--l2-fg-3)" }}>↑↓ navegar</kbd>
                                <kbd className="text-[10px] px-1.5 py-0.5 rounded font-mono" style={{ background: "rgba(34,40,56,0.65)", border: "1px solid var(--l2-hairline)", color: "var(--l2-fg-3)" }}>enter abrir</kbd>
                                <kbd className="text-[10px] px-1.5 py-0.5 rounded font-mono" style={{ background: "rgba(34,40,56,0.65)", border: "1px solid var(--l2-hairline)", color: "var(--l2-fg-3)" }}>esc fechar</kbd>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Modals invocation */}
            {showExpense && <ExpenseModal isOpen={true} onClose={() => setShowExpense(false)} onSave={async () => setShowExpense(false)} />}
            {showInvoice && <InvoiceModal isOpen={true} onClose={() => setShowInvoice(false)} onSave={async () => setShowInvoice(false)} />}
            {showClient && <ClientModal isOpen={true} onClose={() => setShowClient(false)} onSave={async () => setShowClient(false)} />}

            {/* Floating Action Button (Alternative trigger) */}
            {!open && (
                <button
                    onClick={() => setOpen(true)}
                    className="fixed bottom-6 right-6 w-12 h-12 text-white rounded-full flex items-center justify-center z-50 transition-all cursor-pointer group"
                    style={{ background: "var(--atlas-celestial)", boxShadow: "0 4px 12px rgba(79,139,255,0.3)" }}
                    title="Cmd+K"
                    onMouseEnter={(e) => { e.currentTarget.style.transform = "scale(1.08)"; e.currentTarget.style.background = "var(--color-primary-hover)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.transform = "scale(1)"; e.currentTarget.style.background = "var(--atlas-celestial)"; }}
                >
                    <Command className="w-5 h-5" />
                </button>
            )}
        </>
    );
}
