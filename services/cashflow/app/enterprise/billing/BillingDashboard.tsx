"use client";

import { formatCurrency } from "@/lib/utils";
import { DollarSign, CreditCard, ArrowRightLeft, Building2, Users } from "lucide-react";
import StatCard from "@/components/StatCard";

interface BillingDashboardProps {
  totals: {
    gross_revenue: number;
    total_gateway_fees: number;
    total_net: number;
    total_l2_share: number;
    total_client_share: number;
    total_events: number;
  };
  activeSubscriptions: any[];
  recentEvents: any[];
}

export default function BillingDashboard({ totals, activeSubscriptions, recentEvents }: BillingDashboardProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Stat Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 20 }}>
        <StatCard
          title="Receita Bruta Plus"
          value={formatCurrency(totals.gross_revenue)}
          icon={DollarSign}
          accentColor="success"
          trend={{ value: `${totals.total_events} cobranças`, positive: true }}
        />
        <StatCard
          title="Taxas Gateway"
          value={formatCurrency(totals.total_gateway_fees)}
          icon={CreditCard}
          accentColor="danger"
        />
        <StatCard
          title="Repasse L2"
          value={formatCurrency(totals.total_l2_share)}
          icon={ArrowRightLeft}
          accentColor="primary"
        />
        <StatCard
          title="Repasse Cliente"
          value={formatCurrency(totals.total_client_share)}
          icon={Building2}
          accentColor="cyan"
        />
      </div>

      {/* Assinaturas Ativas */}
      <div style={{ background: "rgba(24,28,38,0.55)", padding: 24, borderRadius: 12, border: "1px solid var(--l2-hairline)" }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: "var(--l2-fg-1)", margin: "0 0 16px 0", display: "flex", alignItems: "center", gap: 8 }}>
          <Users size={18} /> Assinaturas Plus Ativas ({activeSubscriptions.length})
        </h2>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--l2-hairline)", color: "var(--l2-fg-2)", textAlign: "left" }}>
                <th style={{ padding: "12px 0", fontWeight: 500 }}>Aluno</th>
                <th style={{ padding: "12px 0", fontWeight: 500 }}>Plano</th>
                <th style={{ padding: "12px 0", fontWeight: 500 }}>Gateway</th>
                <th style={{ padding: "12px 0", fontWeight: 500, textAlign: "right" }}>Valor</th>
                <th style={{ padding: "12px 0", fontWeight: 500, textAlign: "right" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {activeSubscriptions.map((sub: any) => (
                <tr key={sub.id} style={{ borderBottom: "1px solid var(--l2-hairline)" }}>
                  <td style={{ padding: "12px 0", color: "var(--l2-fg-1)", fontWeight: 500 }}>{sub.user_id}</td>
                  <td style={{ padding: "12px 0", color: "var(--l2-fg-2)" }}>{sub.plan_name}</td>
                  <td style={{ padding: "12px 0", color: "var(--l2-fg-2)", textTransform: "capitalize" }}>{sub.gateway || "—"}</td>
                  <td style={{ padding: "12px 0", color: "var(--atlas-cyan)", textAlign: "right", fontWeight: 600 }} className="font-mono">{formatCurrency(sub.price_brl)}</td>
                  <td style={{ padding: "12px 0", textAlign: "right" }}>
                    <span style={{
                      background: sub.status === 'active' ? "rgba(52,211,153,0.15)" : "rgba(248,113,113,0.15)",
                      color: sub.status === 'active' ? "var(--atlas-cyan)" : "var(--sig-crimson)",
                      padding: "3px 10px", borderRadius: 12, fontSize: 12, fontWeight: 600
                    }}>
                      {sub.status === 'active' ? 'Ativo' : sub.status}
                    </span>
                  </td>
                </tr>
              ))}
              {activeSubscriptions.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ padding: "24px 0", textAlign: "center", color: "var(--l2-fg-2)" }}>Nenhuma assinatura Plus registrada.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Eventos Recentes */}
      <div style={{ background: "rgba(24,28,38,0.55)", padding: 24, borderRadius: 12, border: "1px solid var(--l2-hairline)" }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: "var(--l2-fg-1)", margin: "0 0 16px 0" }}>Eventos de Billing Recentes</h2>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--l2-hairline)", color: "var(--l2-fg-2)", textAlign: "left" }}>
                <th style={{ padding: "12px 0", fontWeight: 500 }}>Tipo</th>
                <th style={{ padding: "12px 0", fontWeight: 500 }}>Aluno</th>
                <th style={{ padding: "12px 0", fontWeight: 500, textAlign: "right" }}>Bruto</th>
                <th style={{ padding: "12px 0", fontWeight: 500, textAlign: "right" }}>Taxa GW</th>
                <th style={{ padding: "12px 0", fontWeight: 500, textAlign: "right" }}>L2</th>
                <th style={{ padding: "12px 0", fontWeight: 500, textAlign: "right" }}>Cliente</th>
              </tr>
            </thead>
            <tbody>
              {recentEvents.map((evt: any) => (
                <tr key={evt.id} style={{ borderBottom: "1px solid var(--l2-hairline)" }}>
                  <td style={{ padding: "12px 0", color: "var(--l2-fg-1)" }}>
                    <span style={{
                      background: evt.event_type === 'payment_received' ? "rgba(52,211,153,0.15)" : "rgba(248,113,113,0.15)",
                      color: evt.event_type === 'payment_received' ? "var(--atlas-cyan)" : "var(--sig-crimson)",
                      padding: "3px 8px", borderRadius: 8, fontSize: 11, fontWeight: 600
                    }}>
                      {evt.event_type === 'payment_received' ? 'Pagamento' : evt.event_type}
                    </span>
                  </td>
                  <td style={{ padding: "12px 0", color: "var(--l2-fg-2)" }}>{evt.user_id || "—"}</td>
                  <td style={{ padding: "12px 0", color: "var(--l2-fg-1)", textAlign: "right" }} className="font-mono">{formatCurrency(evt.amount_brl)}</td>
                  <td style={{ padding: "12px 0", color: "var(--sig-crimson)", textAlign: "right" }} className="font-mono">-{formatCurrency(evt.gateway_fee_brl)}</td>
                  <td style={{ padding: "12px 0", color: "var(--atlas-celestial)", textAlign: "right" }} className="font-mono">{formatCurrency(evt.l2_share_brl)}</td>
                  <td style={{ padding: "12px 0", color: "var(--atlas-celestial)", textAlign: "right" }} className="font-mono">{formatCurrency(evt.client_share_brl)}</td>
                </tr>
              ))}
              {recentEvents.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ padding: "24px 0", textAlign: "center", color: "var(--l2-fg-2)" }}>Nenhum evento neste mês.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
