import { ArrowDownRight, ArrowUpRight, Clock } from "lucide-react";
import { Expense, Invoice } from "@/lib/types";
import { formatCurrency } from "@/lib/utils";

interface LiveCommandFeedProps {
    expenses: Expense[];
    invoices: Invoice[];
}

export default function LiveCommandFeed({ expenses, invoices }: LiveCommandFeedProps) {
    // Combine both expenses and invoices into a "Feed Event" list
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
        <div className="l2-border rounded-xl p-6 h-full flex flex-col" style={{ background: "#1A1D26" }}>

            <div className="flex items-center gap-2 mb-6">
                <div className="w-2 h-2 rounded-full" style={{ background: "#34D399" }} />
                <h3 className="text-sm font-semibold uppercase tracking-wider" style={{ color: "#F1F3F6" }}>Atividade Recente</h3>
            </div>

            <div className="flex-1 overflow-y-auto pr-3 -mr-3">
                <div className="ml-2 space-y-1">
                    {events.length === 0 ? (
                        <div className="text-center text-sm py-10" style={{ color: "#5C6478" }}>Nenhuma atividade recente.</div>
                    ) : (
                        events.map((ev) => {
                            const isExpense = ev.type === 'expense';
                            const isIncome = ev.type === 'invoice' && ev.status === 'pago';

                            return (
                                <div
                                    key={ev.id}
                                    className="relative pl-6 py-3 pr-4 rounded-lg transition-colors"
                                    style={{ borderLeft: "2px solid #2E3340" }}
                                    onMouseEnter={(e) => { e.currentTarget.style.background = "#1F2230"; }}
                                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                                >
                                    {/* Timeline Dot */}
                                    <div className="absolute rounded-full"
                                        style={{
                                            left: -5, top: 18, width: 8, height: 8,
                                            background: isExpense ? '#F87171' : isIncome ? '#34D399' : '#FBBF24',
                                        }} />

                                    <div className="flex justify-between items-start">
                                        <div className="flex-1 min-w-0">
                                            <p className="text-xs font-semibold truncate flex items-center gap-1.5" style={{ color: "#F1F3F6" }}>
                                                {isExpense ? <ArrowUpRight className="w-3 h-3" style={{ color: "#F87171" }} /> : isIncome ? <ArrowDownRight className="w-3 h-3" style={{ color: "#34D399" }} /> : <Clock className="w-3 h-3" style={{ color: "#FBBF24" }} />}
                                                {ev.title}
                                            </p>
                                            <p className="text-[10px] truncate mt-0.5" style={{ color: "#9CA3B4" }}>{ev.desc}</p>
                                        </div>
                                        <div className="text-right flex-shrink-0 ml-3">
                                            <p className={`text-xs font-mono font-bold`} style={{ color: isExpense ? '#F87171' : isIncome ? '#34D399' : '#9CA3B4' }}>
                                                {isExpense ? '-' : '+'}{formatCurrency(ev.amount)}
                                            </p>
                                            <p className="text-[9px] mt-0.5 font-mono" style={{ color: "#5C6478" }}>
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
