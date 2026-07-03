import { getAuditLog, getSystemUsers } from "@/lib/db/audit";
import AuditDashboard from "./AuditDashboard";

export default async function AuditPage() {
  const logs = getAuditLog();
  const users = getSystemUsers();

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <header style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--l2-fg-1)", margin: "0 0 8px 0" }}>Auditoria e Segurança</h1>
        <p style={{ color: "var(--l2-fg-2)", margin: 0, fontSize: 14 }}>
          Controle de acesso (RBAC) e registro de atividades sensíveis.
        </p>
      </header>

      <AuditDashboard logs={logs} users={users} />
    </div>
  );
}
