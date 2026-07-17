import { ArrowDownRight, ArrowUpRight, Clock } from "lucide-react";
import { Expense, Invoice } from "@/lib/types";
import { formatCurrency } from "@/lib/utils";

interface LiveCommandFeedProps {
    expenses: Expense[];
    invoices: Invoice[];
}

export default function LiveCommandFeed({ expenses, invoices }: LiveCommandFeedProps) {
    const events = [
        ...expenses.map(e => ({
            id: `exp-${e.id}`,
            type: 'expense' as const,
            amount: e.amount,
            date: new Date(e.date),
            title: `Despesa: ${e.category}`,
            desc: e.description || "Pagamento efetuado",
        })),
        ...invoices.map(i => ({
            id: `inv-${i.id}`,
            type: 'invoice' as const,
            amount: i.amount,
            date: new Date(i.paidDate || i.issueDate),
            title: i.status === 'pago' ? 'Fatura Recebida' : 'Fatura Emitida',
            desc: i.description,
            status: i.status
        }))
    ].sort((a, b) => b.date.getTime() - a.date.getTime()).slice(0, 6);

    return (
        <div data-topo="good" className={`topo-surface topo-shelf dashboard-activity-panel p-5 flex flex-col ${events.length === 0 ? "is-empty" : ""}`}>

            <div className="flex items-center gap-2 mb-6">
                <div className="w-2 h-2 rounded-full" style={{
                    background: "var(--emerald-core)",
                    boxShadow: "0 0 8px var(--emerald-glow)",
                }} />
                <h3 className="text-sm font-semibold uppercase tracking-wider" style={{
                    color: "oklch(0.95 0.01 200)",
                    fontFamily: "var(--font-mono)",
                    letterSpacing: "0.12em",
                }}>
                    Atividade Recente
                </h3>
            </div>

            <div className="flex-1 overflow-y-auto pr-3 -mr-3">
                <div className="ml-2 space-y-1">
                    {events.length === 0 ? (
                        <div className="dashboard-empty-state text-center text-sm" style={{ color: "oklch(0.50 0.02 200)" }}>
                            Nenhuma atividade recente.
                        </div>
                    ) : (
                        events.map((ev) => {
                            const isExpense = ev.type === 'expense';
                            const isIncome = ev.type === 'invoice' && ev.status === 'pago';

                            return (
                                <div
                                    key={ev.id}
                                    className="relative pl-6 py-3 pr-4 rounded-sm transition-all"
                                    style={{
                                        borderLeft: "2px solid oklch(1 0 0 / 5%)",
                                        cursor: "default",
                                    }}
                                    onMouseEnter={(e) => {
                                        e.currentTarget.style.background = "oklch(1 0 0 / 3%)";
                                        e.currentTarget.style.borderLeftColor = isExpense
                                            ? "var(--sig-crimson)"
                                            : isIncome
                                                ? "var(--emerald-core)"
                                                : "var(--sig-amber)";
                                    }}
                                    onMouseLeave={(e) => {
                                        e.currentTarget.style.background = "transparent";
                                        e.currentTarget.style.borderLeftColor = "oklch(1 0 0 / 5%)";
                                    }}
                                >
                                    {/* Timeline Dot */}
                                    <div className="absolute rounded-full"
                                        style={{
                                            left: -5, top: 18, width: 8, height: 8,
                                            background: isExpense
                                                ? 'var(--sig-crimson)'
                                                : isIncome
                                                    ? 'var(--emerald-core)'
                                                    : 'var(--sig-amber)',
                                            boxShadow: `0 0 6px ${isExpense
                                                ? 'rgba(255,0,85,0.4)'
                                                : isIncome
                                                    ? 'rgba(70,240,224,0.4)'
                                                    : 'rgba(255,214,0,0.4)'}`,
                                        }} />

                                    <div className="flex justify-between items-start">
                                        <div className="flex-1 min-w-0">
                                            <p className="text-xs font-semibold truncate flex items-center gap-1.5" style={{ color: "oklch(0.95 0.01 200)" }}>
                                                {isExpense
                                                    ? <ArrowUpRight className="w-3 h-3" style={{ color: "var(--sig-crimson)" }} />
                                                    : isIncome
                                                        ? <ArrowDownRight className="w-3 h-3" style={{ color: "var(--emerald-core)" }} />
                                                        : <Clock className="w-3 h-3" style={{ color: "var(--sig-amber)" }} />}
                                                {ev.title}
                                            </p>
                                            <p className="text-[10px] truncate mt-0.5" style={{ color: "oklch(0.72 0.02 200)" }}>{ev.desc}</p>
                                        </div>
                                        <div className="text-right flex-shrink-0 ml-3">
                                            <p className="text-xs font-mono font-bold" style={{
                                                color: isExpense
                                                    ? 'var(--sig-crimson)'
                                                    : isIncome
                                                        ? 'var(--emerald-core)'
                                                        : 'oklch(0.72 0.02 200)',
                                            }}>
                                                {isExpense ? '-' : '+'}{formatCurrency(ev.amount)}
                                            </p>
                                            <p className="text-[9px] mt-0.5 font-mono" style={{ color: "oklch(0.50 0.02 200)" }}>
                                                {ev.date.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' }).replace('.', '')}
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>
            </div>
        </div>
    );
}
