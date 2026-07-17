"use client";

import { useState } from "react";
import { ShieldCheck, Activity, Users } from "lucide-react";
import StatCard from "@/components/StatCard";

interface AuditDashboardProps {
  logs: any[];
  users: any[];
}

export default function AuditDashboard({ logs, users }: AuditDashboardProps) {
  const [filterAction, setFilterAction] = useState("");
  const [filterEntity, setFilterEntity] = useState("");

  const filteredLogs = logs.filter(log => {
    if (filterAction && log.action !== filterAction) return false;
    if (filterEntity && log.entity_type !== filterEntity) return false;
    return true;
  });

  const getActionIcon = (action: string) => {
    switch (action) {
      case 'create': return <span style={{ color: "var(--atlas-cyan)" }}>+ Criação</span>;
      case 'update': return <span style={{ color: "var(--sig-amber)" }}>~ Edição</span>;
      case 'delete': return <span style={{ color: "var(--sig-crimson)" }}>- Exclusão</span>;
      case 'login': return <span style={{ color: "var(--atlas-celestial)" }}>&gt; Login</span>;
      case 'export': return <span style={{ color: "var(--atlas-violet)" }}>↓ Exportação</span>;
      default: return <span style={{ color: "var(--l2-fg-2)" }}>{action}</span>;
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Stat Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 20 }}>
        <StatCard
          title="Total de Eventos (Mês)"
          value={logs.length.toString()}
          icon={Activity}
          accentColor="primary"
        />
        <StatCard
          title="Usuários Ativos"
          value={users.filter(u => u.active).length.toString()}
          icon={Users}
          accentColor="success"
        />
        <StatCard
          title="Edições Críticas"
          value={logs.filter(l => l.action === 'update' || l.action === 'delete').length.toString()}
          icon={ShieldCheck}
          accentColor="warning"
        />
      </div>

      <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
        {/* Main Log Table */}
        <div style={{ flex: 3, background: "rgba(24,28,38,0.55)", padding: 24, borderRadius: 12, border: "1px solid var(--l2-hairline)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <h2 style={{ fontSize: 16, fontWeight: 600, color: "var(--l2-fg-1)", margin: 0 }}>Histórico de Atividades</h2>

            <div style={{ display: "flex", gap: 12 }}>
              <select
                value={filterAction}
                onChange={e => setFilterAction(e.target.value)}
                style={{ padding: "6px 12px", borderRadius: 6, background: "var(--l2-void-deep)", border: "1px solid var(--l2-hairline)", color: "var(--l2-fg-1)", fontSize: 13 }}
              >
                <option value="">Todas as ações</option>
                <option value="create">Criação</option>
                <option value="update">Edição</option>
                <option value="delete">Exclusão</option>
                <option value="login">Login</option>
                <option value="export">Exportação</option>
              </select>

              <select
                value={filterEntity}
                onChange={e => setFilterEntity(e.target.value)}
                style={{ padding: "6px 12px", borderRadius: 6, background: "var(--l2-void-deep)", border: "1px solid var(--l2-hairline)", color: "var(--l2-fg-1)", fontSize: 13 }}
              >
                <option value="">Todas as entidades</option>
                <option value="contract">Contratos</option>
                <option value="client_account">Clientes</option>
                <option value="plus_subscription">Assinaturas</option>
                <option value="report">Relatórios</option>
                <option value="system">Sistema</option>
              </select>
            </div>
          </div>

          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--l2-hairline)", color: "var(--l2-fg-2)", textAlign: "left" }}>
                  <th style={{ padding: "12px 0", fontWeight: 500 }}>Data/Hora</th>
                  <th style={{ padding: "12px 0", fontWeight: 500 }}>Usuário</th>
                  <th style={{ padding: "12px 0", fontWeight: 500 }}>Ação</th>
                  <th style={{ padding: "12px 0", fontWeight: 500 }}>Entidade</th>
                  <th style={{ padding: "12px 0", fontWeight: 500 }}>Detalhes</th>
                  <th style={{ padding: "12px 0", fontWeight: 500, textAlign: "right" }}>IP</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.map((log: any) => (
                  <tr key={log.id} style={{ borderBottom: "1px solid var(--l2-hairline)" }}>
                    <td style={{ padding: "12px 0", color: "var(--l2-fg-2)" }} className="font-mono">
                      {new Date(log.created_at).toLocaleString('pt-BR')}
                    </td>
                    <td style={{ padding: "12px 0", color: "var(--l2-fg-1)", fontWeight: 500 }}>{log.user_email}</td>
                    <td style={{ padding: "12px 0", fontWeight: 600 }}>{getActionIcon(log.action)}</td>
                    <td style={{ padding: "12px 0", color: "var(--l2-fg-2)" }}>{log.entity_type} {log.entity_id ? `(${log.entity_id})` : ''}</td>
                    <td style={{ padding: "12px 0", color: "var(--l2-fg-2)", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {log.details_json ? JSON.stringify(JSON.parse(log.details_json)) : '—'}
                    </td>
                    <td style={{ padding: "12px 0", color: "var(--l2-fg-2)", textAlign: "right" }} className="font-mono">{log.ip_address}</td>
                  </tr>
                ))}
                {filteredLogs.length === 0 && (
                  <tr>
                    <td colSpan={6} style={{ padding: "24px 0", textAlign: "center", color: "var(--l2-fg-2)" }}>Nenhum log encontrado para os filtros selecionados.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Users Sidebar */}
        <div style={{ flex: 1, background: "rgba(24,28,38,0.55)", padding: 24, borderRadius: 12, border: "1px solid var(--l2-hairline)" }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: "var(--l2-fg-1)", margin: "0 0 16px 0", display: "flex", alignItems: "center", gap: 8 }}>
            <Users size={18} /> Usuários do Sistema
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {users.map(u => (
              <div key={u.id} style={{ padding: 12, background: "var(--l2-void-deep)", borderRadius: 8, border: "1px solid var(--l2-hairline)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                  <span style={{ color: "var(--l2-fg-1)", fontWeight: 600, fontSize: 13 }}>{u.name}</span>
                  <span style={{
                    fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 12,
                    background: u.role === 'admin' ? "rgba(79,139,255,0.15)" : "rgba(156,163,180,0.1)",
                    color: u.role === 'admin' ? "var(--color-primary-hover)" : "var(--l2-fg-2)"
                  }}>
                    {u.role.toUpperCase()}
                  </span>
                </div>
                <p style={{ color: "var(--l2-fg-2)", fontSize: 12, margin: "0 0 8px 0" }}>{u.email}</p>
                <p style={{ color: "var(--l2-fg-3)", fontSize: 11, margin: 0 }}>Último login: {u.last_login ? new Date(u.last_login).toLocaleDateString() : 'Nunca'}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
