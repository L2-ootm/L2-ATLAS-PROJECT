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
                    <h1 className="text-2xl font-bold" style={{ color: "#F1F3F6" }}>Clientes</h1>
                    <p className="text-sm mt-0.5" style={{ color: "#5C6478" }}>Gerencie seus clientes e contratos</p>
                </div>
                <button onClick={() => { setEditingClient(null); setShowModal(true); }}
                    style={{
                        display: "flex", alignItems: "center", gap: 8,
                        padding: "10px 24px",
                        background: "#6366F1", color: "white",
                        borderRadius: 8, fontWeight: 600, fontSize: 14,
                        border: "none", cursor: "pointer",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                        transition: "background 200ms",
                        flexShrink: 0,
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "#818CF8"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "#6366F1"; }}>
                    <Plus style={{ width: 16, height: 16 }} /> Novo Cliente
                </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <StatCard title="Clientes Ativos" value={String(activeCount)} icon={Users} accentColor="cyan" />
                <StatCard title="Receita Mensal Total" value={formatCurrency(totalRevenue)} icon={DollarSign} accentColor="violet" />
            </div>

            <div className="flex flex-col sm:flex-row gap-3">
                <div style={{ position: "relative", flex: 1 }}>
                    <Search style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", width: 16, height: 16, color: "#5C6478" }} />
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
                        border: "1px solid #2E3340",
                        background: showInactive ? "#252937" : "transparent",
                        color: showInactive ? "#F1F3F6" : "#9CA3B4",
                        cursor: "pointer",
                        transition: "all 200ms",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "#252937"; e.currentTarget.style.color = "#F1F3F6"; }}
                    onMouseLeave={(e) => {
                        if (!showInactive) { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "#9CA3B4"; }
                    }}>
                    {showInactive ? "Mostrando inativos" : "Mostrar inativos"}
                </button>
            </div>

            <div className="l2-border rounded-xl overflow-hidden" style={{ background: "#1A1D26" }}>
                <div className="hidden md:grid grid-cols-12 gap-4 text-[10px] font-semibold uppercase tracking-wider font-mono"
                    style={{ borderBottom: "1px solid #2E3340", padding: "14px 24px", color: "#5C6478", background: "#1F2230" }}>
                    <div className="col-span-3">Cliente</div>
                    <div className="col-span-3">Serviço</div>
                    <div className="col-span-2">Valor Mensal</div>
                    <div className="col-span-1">Status</div>
                    <div className="col-span-2">Início</div>
                    <div className="col-span-1 text-right">Ações</div>
                </div>

                {filtered.length === 0 ? (
                    <div className="text-center py-12">
                        <p className="text-sm" style={{ color: "#5C6478" }}>{search ? "Nenhum cliente encontrado" : "Nenhum cliente cadastrado"}</p>
                    </div>
                ) : (
                    <div>
                        {filtered.map((client, i) => (
                            <div key={client.id}
                                className="grid grid-cols-1 md:grid-cols-12 gap-2 md:gap-4 items-center transition-colors"
                                style={{ padding: "16px 24px", borderBottom: i < filtered.length - 1 ? "1px solid #252937" : "none" }}
                                onMouseEnter={(e) => { e.currentTarget.style.background = "#1F2230"; }}
                                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}>
                                <div className="md:col-span-3">
                                    <p className="text-sm font-semibold" style={{ color: "#F1F3F6" }}>{client.name}</p>
                                    <p className="text-xs md:hidden" style={{ color: "#5C6478" }}>{client.service}</p>
                                </div>
                                <div className="hidden md:block md:col-span-3"><p className="text-sm" style={{ color: "#9CA3B4" }}>{client.service}</p></div>
                                <div className="md:col-span-2"><p className="text-sm font-semibold font-mono" style={{ color: "#6366F1" }}>{formatCurrency(client.monthlyPayment)}</p></div>
                                <div className="md:col-span-1">
                                    {client.active
                                        ? <span className="badge-active inline-flex items-center gap-1 text-[10px] font-medium px-2 py-1 rounded-full"><CheckCircle2 className="w-3 h-3" /> Ativo</span>
                                        : <span className="badge-inactive inline-flex items-center gap-1 text-[10px] font-medium px-2 py-1 rounded-full"><XCircle className="w-3 h-3" /> Inativo</span>}
                                </div>
                                <div className="hidden md:block md:col-span-2"><p className="text-sm font-mono" style={{ color: "#9CA3B4" }}>{formatDate(client.startDate)}</p></div>
                                <div className="md:col-span-1 flex items-center justify-end gap-1">
                                    <button onClick={() => { setEditingClient(client); setShowModal(true); }}
                                        className="p-2 rounded-lg transition-colors" title="Editar"
                                        style={{ color: "#5C6478" }}
                                        onMouseEnter={(e) => { e.currentTarget.style.background = "#252937"; e.currentTarget.style.color = "#F1F3F6"; }}
                                        onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "#5C6478"; }}>
                                        <Edit2 className="w-4 h-4" />
                                    </button>
                                    {deleteConfirm === client.id
                                        ? <button onClick={() => handleDelete(client.id)} className="p-2 rounded-lg" title="Confirmar"
                                            style={{ color: "#F87171", background: "rgba(248,113,113,0.1)" }}><Trash2 className="w-4 h-4" /></button>
                                        : <button onClick={() => setDeleteConfirm(client.id)} className="p-2 rounded-lg transition-colors" title="Excluir"
                                            style={{ color: "#5C6478" }}
                                            onMouseEnter={(e) => { e.currentTarget.style.color = "#F87171"; e.currentTarget.style.background = "#252937"; }}
                                            onMouseLeave={(e) => { e.currentTarget.style.color = "#5C6478"; e.currentTarget.style.background = "transparent"; }}>
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
