"use client";

import { useState, useEffect, useMemo } from "react";
import { Plus, Search, Edit2, Trash2, Users, DollarSign, CheckCircle2, XCircle } from "lucide-react";
import StatCard from "@/components/StatCard";
import ClientModal from "@/components/ClientModal";
import { Client } from "@/lib/types";
import { getClients, addClient, updateClient, deleteClient } from "@/app/actions";
import { formatCurrency, formatDate } from "@/lib/utils";

export default function ClientesPage() {
    const [clients, setClients] = useState<Client[]>([]);
    const [search, setSearch] = useState("");
    const [showModal, setShowModal] = useState(false);
    const [editingClient, setEditingClient] = useState<Client | null>(null);
    const [showInactive, setShowInactive] = useState(false);
    const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

    useEffect(() => {
        getClients().then(setClients);
    }, []);

    const filtered = useMemo(() => {
        let list = clients;
        if (!showInactive) list = list.filter((c) => c.active);
        if (search) {
            const q = search.toLowerCase();
            list = list.filter((c) => c.name.toLowerCase().includes(q) || c.service.toLowerCase().includes(q));
        }
        return list.sort((a, b) => a.name.localeCompare(b.name));
    }, [clients, search, showInactive]);

    const activeCount = useMemo(() => clients.filter((c) => c.active).length, [clients]);
    const totalRevenue = useMemo(() => clients.filter((c) => c.active).reduce((s, c) => s + c.monthlyPayment, 0), [clients]);

    const handleSave = async (client: Client) => {
        if (editingClient) {
            await updateClient(client);
        } else {
            await addClient(client);
        }
        setClients(await getClients());
    };

    const handleDelete = async (id: string) => {
        await deleteClient(id);
        setClients(await getClients());
        setDeleteConfirm(null);
    };

    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold" style={{ color: "var(--l2-fg-1)" }}>Clientes</h1>
                    <p className="text-sm mt-0.5" style={{ color: "var(--l2-fg-3)" }}>Gerencie seus clientes e contratos</p>
                </div>
                <button onClick={() => { setEditingClient(null); setShowModal(true); }}
                    style={{
                        display: "flex", alignItems: "center", gap: 8,
                        padding: "10px 24px",
                        background: "rgba(79,139,255,0.14)", color: "#9CC0FF",
                        borderRadius: 8, fontWeight: 600, fontSize: 14,
                        border: "1px solid rgba(79,139,255,0.38)", cursor: "pointer",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                        transition: "background 200ms",
                        flexShrink: 0,
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(79,139,255,0.24)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(79,139,255,0.14)"; }}>
                    <Plus style={{ width: 16, height: 16 }} /> Novo Cliente
                </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <StatCard title="Clientes Ativos" value={String(activeCount)} icon={Users} accentColor="cyan" />
                <StatCard title="Receita Mensal Total" value={formatCurrency(totalRevenue)} icon={DollarSign} accentColor="violet" />
            </div>

            <div className="flex flex-col sm:flex-row gap-3">
                <div style={{ position: "relative", flex: 1 }}>
                    <Search style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", width: 16, height: 16, color: "var(--l2-fg-3)" }} />
                    <input type="text" placeholder="Buscar por nome ou serviço..." value={search} onChange={(e) => setSearch(e.target.value)}
                        className="input-l2" style={{ width: "100%", paddingLeft: 40, paddingRight: 16, paddingTop: 10, paddingBottom: 10, borderRadius: 8 }} />
                </div>
                <button onClick={() => setShowInactive(!showInactive)}
                    style={{
                        padding: "10px 20px",
                        borderRadius: 8,
                        fontWeight: 500,
                        fontSize: 14,
                        flexShrink: 0,
                        border: "1px solid var(--l2-hairline)",
                        background: showInactive ? "rgba(34,40,56,0.65)" : "transparent",
                        color: showInactive ? "var(--l2-fg-1)" : "var(--l2-fg-2)",
                        cursor: "pointer",
                        transition: "all 200ms",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(34,40,56,0.65)"; e.currentTarget.style.color = "var(--l2-fg-1)"; }}
                    onMouseLeave={(e) => {
                        if (!showInactive) { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--l2-fg-2)"; }
                    }}>
                    {showInactive ? "Mostrando inativos" : "Mostrar inativos"}
                </button>
            </div>

            <div className="l2-border rounded-sm overflow-hidden" style={{ background: "rgba(24,28,38,0.55)" }}>
                <div className="hidden md:grid grid-cols-12 gap-4 text-[10px] font-semibold uppercase tracking-wider font-mono"
                    style={{ borderBottom: "1px solid var(--l2-hairline)", padding: "14px 24px", color: "var(--l2-fg-3)", background: "rgba(18,21,29,0.65)" }}>
                    <div className="col-span-3">Cliente</div>
                    <div className="col-span-3">Serviço</div>
                    <div className="col-span-2">Valor Mensal</div>
                    <div className="col-span-1">Status</div>
                    <div className="col-span-2">Início</div>
                    <div className="col-span-1 text-right">Ações</div>
                </div>

                {filtered.length === 0 ? (
                    <div className="text-center py-12">
                        <p className="text-sm" style={{ color: "var(--l2-fg-3)" }}>{search ? "Nenhum cliente encontrado" : "Nenhum cliente cadastrado"}</p>
                    </div>
                ) : (
                    <div>
                        {filtered.map((client, i) => (
                            <div key={client.id}
                                className="grid grid-cols-1 md:grid-cols-12 gap-2 md:gap-4 items-center transition-colors"
                                style={{ padding: "16px 24px", borderBottom: i < filtered.length - 1 ? "1px solid rgba(34,40,56,0.65)" : "none" }}
                                onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(18,21,29,0.65)"; }}
                                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}>
                                <div className="md:col-span-3">
                                    <p className="text-sm font-semibold" style={{ color: "var(--l2-fg-1)" }}>{client.name}</p>
                                    <p className="text-xs md:hidden" style={{ color: "var(--l2-fg-3)" }}>{client.service}</p>
                                </div>
                                <div className="hidden md:block md:col-span-3"><p className="text-sm" style={{ color: "var(--l2-fg-2)" }}>{client.service}</p></div>
                                <div className="md:col-span-2"><p className="text-sm font-semibold font-mono" style={{ color: "#4F8BFF" }}>{formatCurrency(client.monthlyPayment)}</p></div>
                                <div className="md:col-span-1">
                                    {client.active
                                        ? <span className="badge-active inline-flex items-center gap-1 text-[10px] font-medium px-2 py-1 rounded-full"><CheckCircle2 className="w-3 h-3" /> Ativo</span>
                                        : <span className="badge-inactive inline-flex items-center gap-1 text-[10px] font-medium px-2 py-1 rounded-full"><XCircle className="w-3 h-3" /> Inativo</span>}
                                </div>
                                <div className="hidden md:block md:col-span-2"><p className="text-sm font-mono" style={{ color: "var(--l2-fg-2)" }}>{formatDate(client.startDate)}</p></div>
                                <div className="md:col-span-1 flex items-center justify-end gap-1">
                                    <button onClick={() => { setEditingClient(client); setShowModal(true); }}
                                        className="p-2 rounded-lg transition-colors" title="Editar"
                                        style={{ color: "var(--l2-fg-3)" }}
                                        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(34,40,56,0.65)"; e.currentTarget.style.color = "var(--l2-fg-1)"; }}
                                        onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--l2-fg-3)"; }}>
                                        <Edit2 className="w-4 h-4" />
                                    </button>
                                    {deleteConfirm === client.id
                                        ? <button onClick={() => handleDelete(client.id)} className="p-2 rounded-lg" title="Confirmar"
                                            style={{ color: "#FF0055", background: "rgba(248,113,113,0.1)" }}><Trash2 className="w-4 h-4" /></button>
                                        : <button onClick={() => setDeleteConfirm(client.id)} className="p-2 rounded-lg transition-colors" title="Excluir"
                                            style={{ color: "var(--l2-fg-3)" }}
                                            onMouseEnter={(e) => { e.currentTarget.style.color = "#FF0055"; e.currentTarget.style.background = "rgba(34,40,56,0.65)"; }}
                                            onMouseLeave={(e) => { e.currentTarget.style.color = "var(--l2-fg-3)"; e.currentTarget.style.background = "transparent"; }}>
                                            <Trash2 className="w-4 h-4" />
                                        </button>}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <ClientModal isOpen={showModal} onClose={() => { setShowModal(false); setEditingClient(null); }} onSave={handleSave} client={editingClient} />
        </div>
    );
}
