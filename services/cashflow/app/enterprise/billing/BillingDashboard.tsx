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
      <div style={{ background: "#1A1D26", padding: 24, borderRadius: 12, border: "1px solid #2E3340" }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: "#F1F3F6", margin: "0 0 16px 0", display: "flex", alignItems: "center", gap: 8 }}>
          <Users size={18} /> Assinaturas Plus Ativas ({activeSubscriptions.length})
        </h2>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #2E3340", color: "#9CA3B4", textAlign: "left" }}>
                <th style={{ padding: "12px 0", fontWeight: 500 }}>Aluno</th>
                <th style={{ padding: "12px 0", fontWeight: 500 }}>Plano</th>
                <th style={{ padding: "12px 0", fontWeight: 500 }}>Gateway</th>
                <th style={{ padding: "12px 0", fontWeight: 500, textAlign: "right" }}>Valor</th>
                <th style={{ padding: "12px 0", fontWeight: 500, textAlign: "right" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {activeSubscriptions.map((sub: any) => (
                <tr key={sub.id} style={{ borderBottom: "1px solid #2E3340" }}>
                  <td style={{ padding: "12px 0", color: "#F1F3F6", fontWeight: 500 }}>{sub.user_id}</td>
                  <td style={{ padding: "12px 0", color: "#9CA3B4" }}>{sub.plan_name}</td>
                  <td style={{ padding: "12px 0", color: "#9CA3B4", textTransform: "capitalize" }}>{sub.gateway || "—"}</td>
                  <td style={{ padding: "12px 0", color: "#34D399", textAlign: "right", fontWeight: 600 }} className="font-mono">{formatCurrency(sub.price_brl)}</td>
                  <td style={{ padding: "12px 0", textAlign: "right" }}>
                    <span style={{
                      background: sub.status === 'active' ? "rgba(52,211,153,0.15)" : "rgba(248,113,113,0.15)",
                      color: sub.status === 'active' ? "#34D399" : "#F87171",
                      padding: "3px 10px", borderRadius: 12, fontSize: 12, fontWeight: 600
                    }}>
                      {sub.status === 'active' ? 'Ativo' : sub.status}
                    </span>
                  </td>
                </tr>
              ))}
              {activeSubscriptions.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ padding: "24px 0", textAlign: "center", color: "#9CA3B4" }}>Nenhuma assinatura Plus registrada.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Eventos Recentes */}
      <div style={{ background: "#1A1D26", padding: 24, borderRadius: 12, border: "1px solid #2E3340" }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: "#F1F3F6", margin: "0 0 16px 0" }}>Eventos de Billing Recentes</h2>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #2E3340", color: "#9CA3B4", textAlign: "left" }}>
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
                <tr key={evt.id} style={{ borderBottom: "1px solid #2E3340" }}>
                  <td style={{ padding: "12px 0", color: "#F1F3F6" }}>
                    <span style={{
                      background: evt.event_type === 'payment_received' ? "rgba(52,211,153,0.15)" : "rgba(248,113,113,0.15)",
                      color: evt.event_type === 'payment_received' ? "#34D399" : "#F87171",
                      padding: "3px 8px", borderRadius: 8, fontSize: 11, fontWeight: 600
                    }}>
                      {evt.event_type === 'payment_received' ? 'Pagamento' : evt.event_type}
                    </span>
                  </td>
                  <td style={{ padding: "12px 0", color: "#9CA3B4" }}>{evt.user_id || "—"}</td>
                  <td style={{ padding: "12px 0", color: "#F1F3F6", textAlign: "right" }} className="font-mono">{formatCurrency(evt.amount_brl)}</td>
                  <td style={{ padding: "12px 0", color: "#F87171", textAlign: "right" }} className="font-mono">-{formatCurrency(evt.gateway_fee_brl)}</td>
                  <td style={{ padding: "12px 0", color: "#6366F1", textAlign: "right" }} className="font-mono">{formatCurrency(evt.l2_share_brl)}</td>
                  <td style={{ padding: "12px 0", color: "#3B82F6", textAlign: "right" }} className="font-mono">{formatCurrency(evt.client_share_brl)}</td>
                </tr>
              ))}
              {recentEvents.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ padding: "24px 0", textAlign: "center", color: "#9CA3B4" }}>Nenhum evento neste mês.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
