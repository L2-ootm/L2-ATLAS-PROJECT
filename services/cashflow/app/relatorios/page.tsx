"use client";

import { useState, useEffect, useMemo } from "react";
import { BarChart3, DollarSign, TrendingDown, TrendingUp, Users, Copy, CheckCircle2, Briefcase, FileDown } from "lucide-react";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import StatCard from "@/components/StatCard";
import MonthSelector from "@/components/MonthSelector";
import { getClients, getExpenses } from "@/app/actions";
import { formatCurrency, getMonthYear, getMonthLabel } from "@/lib/utils";
import { Client, Expense, EXPENSE_CATEGORIES } from "@/lib/types";

export default function RelatoriosPage() {
    const [month, setMonth] = useState(() => getMonthYear(new Date()));
    const [clients, setClients] = useState<Client[]>([]);
    const [expenses, setExpenses] = useState<Expense[]>([]);
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        Promise.all([getClients(), getExpenses()]).then(([cls, exp]) => {
            setClients(cls);
            setExpenses(exp);
        });
    }, []);

    const activeClients = useMemo(() => clients.filter((c) => c.active), [clients]);
    const monthExpenses = useMemo(() => expenses.filter((e) => e.date.startsWith(month)), [expenses, month]);

    const totalRevenue = useMemo(() => activeClients.reduce((s, c) => s + c.monthlyPayment, 0), [activeClients]);
    const totalExpenses = useMemo(() => monthExpenses.reduce((s, e) => s + e.amount, 0), [monthExpenses]);

    const profit = totalRevenue - totalExpenses;
    const margin = totalRevenue > 0 ? ((profit / totalRevenue) * 100).toFixed(1) : "0";

    const clientProfitability = useMemo(() => {
        return activeClients.map((client) => {
            const ce = monthExpenses.filter((e) => e.clientId === client.id).reduce((s, e) => s + e.amount, 0);
            const cp = client.monthlyPayment - ce;
            const cm = client.monthlyPayment > 0 ? ((cp / client.monthlyPayment) * 100).toFixed(1) : "0";
            return { id: client.id, name: client.name, service: client.service, revenue: client.monthlyPayment, expenses: ce, profit: cp, margin: cm };
        }).sort((a, b) => b.profit - a.profit);
    }, [activeClients, monthExpenses]);

    const categoryBreakdown = useMemo(() => {
        const map: Record<string, number> = {};
        monthExpenses.forEach((e) => { map[e.category] = (map[e.category] || 0) + e.amount; });
        return EXPENSE_CATEGORIES.map((cat) => ({
            category: cat, amount: map[cat] || 0,
            percentage: totalExpenses > 0 ? (((map[cat] || 0) / totalExpenses) * 100).toFixed(1) : "0",
        })).filter((c) => c.amount > 0).sort((a, b) => b.amount - a.amount);
    }, [monthExpenses, totalExpenses]);

    const generalExpenses = useMemo(() => monthExpenses.filter((e) => e.clientId === null).reduce((s, e) => s + e.amount, 0), [monthExpenses]);

    // Margem por Serviço
    const serviceMargin = useMemo(() => {
        const serviceMap: Record<string, { revenue: number; expenses: number; count: number }> = {};
        clientProfitability.forEach((cp) => {
            const svc = cp.service || "Sem serviço";
            if (!serviceMap[svc]) serviceMap[svc] = { revenue: 0, expenses: 0, count: 0 };
            serviceMap[svc].revenue += cp.revenue;
            serviceMap[svc].expenses += cp.expenses;
            serviceMap[svc].count++;
        });
        return Object.entries(serviceMap).map(([service, data]) => {
            const sProfit = data.revenue - data.expenses;
            const sMargin = data.revenue > 0 ? ((sProfit / data.revenue) * 100).toFixed(1) : "0";
            return { service, ...data, profit: sProfit, margin: sMargin };
        }).sort((a, b) => b.profit - a.profit);
    }, [clientProfitability]);

    const barClass: Record<string, string> = {
        Software: "bar-software", Marketing: "bar-marketing", Equipamento: "bar-equipamento",
        Infraestrutura: "bar-infraestrutura", Pessoal: "bar-pessoal", Outros: "bar-outros",
    };

    const exportReport = () => {
        const label = getMonthLabel(month);
        let text = `⚡ RELATÓRIO L2 — ${label}\n${"═".repeat(40)}\n\n`;
        text += `💰 Faturamento: ${formatCurrency(totalRevenue)}\n📉 Despesas: ${formatCurrency(totalExpenses)}\n📈 Lucro: ${formatCurrency(profit)}\n📊 Margem: ${margin}%\n\n`;
        text += `👥 POR CLIENTE\n${"-".repeat(35)}\n`;
        clientProfitability.forEach((c) => { text += `• ${c.name}: ${formatCurrency(c.profit)} (${c.margin}%)\n`; });
        text += `\n💸 Gerais L2: ${formatCurrency(generalExpenses)}\n\n📂 POR CATEGORIA\n${"-".repeat(35)}\n`;
        categoryBreakdown.forEach((c) => { text += `• ${c.category}: ${formatCurrency(c.amount)} (${c.percentage}%)\n`; });
        text += `\n🔧 POR SERVIÇO\n${"-".repeat(35)}\n`;
        serviceMargin.forEach((s) => { text += `• ${s.service}: ${formatCurrency(s.profit)} (${s.margin}% margem, ${s.count} cliente${s.count > 1 ? "s" : ""})\n`; });
        navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); });
    };

    const downloadPDF = () => {
        const doc = new jsPDF();
        const label = getMonthLabel(month);

        const colorRed = [220, 38, 38] as [number, number, number]; // red-600
        const colorGreen = [5, 150, 105] as [number, number, number]; // emerald-600
        const colorNeutral = [17, 24, 39] as [number, number, number]; // gray-900

        const getCategoryColor = (cat: string): [number, number, number] => {
            switch (cat) {
                case 'Software': return [99, 102, 241]; // indigo-500
                case 'Marketing': return [245, 158, 11]; // amber-500
                case 'Equipamento': return [16, 185, 129]; // emerald-500
                case 'Infraestrutura': return [100, 116, 139]; // slate-500
                case 'Pessoal': return [168, 85, 247]; // purple-500
                default: return [107, 114, 128]; // gray-500 (Outros)
            }
        };

        const parseNetMarginColor = (valStr: string) => {
            if (valStr.includes('-')) return colorRed;
            if (valStr.replace(/[^0-9.]/g, '') === '0.0' || valStr.replace(/[^0-9.]/g, '') === '0') return colorNeutral;
            return colorGreen;
        };

        // Header
        doc.setFontSize(18);
        doc.setTextColor(30, 30, 30);
        doc.text(`Relatório L2 Financeiro - ${label}`, 14, 20);

        // Resumo
        doc.setFontSize(11);
        doc.setTextColor(60, 60, 60);
        doc.text(`Faturamento: ${formatCurrency(totalRevenue)}`, 14, 30);
        doc.text(`Despesas: `, 14, 36);
        doc.setTextColor(...colorRed);
        doc.text(`${formatCurrency(totalExpenses)}`, 34, 36);

        doc.setTextColor(60, 60, 60);
        doc.text(`Lucro Líquido: `, 14, 42);
        doc.setTextColor(...(profit >= 0 ? colorGreen : colorRed));
        doc.text(`${formatCurrency(profit)}`, 41, 42);

        doc.setTextColor(60, 60, 60);
        doc.text(`Margem: `, 14, 48);
        doc.setTextColor(...(parseFloat(margin) >= 0 ? colorGreen : colorRed));
        doc.text(`${margin}%`, 31, 48);

        // Tabela Clientes
        autoTable(doc, {
            startY: 55,
            head: [['Cliente', 'Receita', 'Despesas', 'Lucro', 'Margem']],
            body: clientProfitability.map(c => [
                c.name,
                formatCurrency(c.revenue),
                formatCurrency(c.expenses),
                formatCurrency(c.profit),
                `${c.margin}%`
            ]),
            didParseCell: (data) => {
                if (data.section === 'body') {
                    if (data.column.index === 1) data.cell.styles.textColor = colorNeutral; // Receita
                    if (data.column.index === 2) data.cell.styles.textColor = colorRed; // Despesas
                    if (data.column.index === 3) data.cell.styles.textColor = parseNetMarginColor(data.cell.text[0]); // Lucro
                    if (data.column.index === 4) data.cell.styles.textColor = parseNetMarginColor(data.cell.text[0]); // Margem
                }
            }
        });

        // Tabela Categorias
        autoTable(doc, {
            startY: (doc as any).lastAutoTable.finalY + 10,
            head: [['Categoria', 'Valor', '% Total']],
            body: categoryBreakdown.map(c => [
                c.category,
                formatCurrency(c.amount),
                `${c.percentage}%`
            ]),
            didParseCell: (data) => {
                if (data.section === 'body') {
                    const rowCat = categoryBreakdown[data.row.index].category;
                    data.cell.styles.textColor = getCategoryColor(rowCat);
                }
            }
        });

        // Tabela Serviços
        autoTable(doc, {
            startY: (doc as any).lastAutoTable.finalY + 10,
            head: [['Serviço', 'Clientes', 'Receita', 'Despesas', 'Lucro', 'Margem']],
            body: serviceMargin.map(s => [
                s.service,
                s.count.toString(),
                formatCurrency(s.revenue),
                formatCurrency(s.expenses),
                formatCurrency(s.profit),
                `${s.margin}%`
            ]),
            didParseCell: (data) => {
                if (data.section === 'body') {
                    if (data.column.index === 2) data.cell.styles.textColor = colorNeutral; // Receita
                    if (data.column.index === 3) data.cell.styles.textColor = colorRed; // Despesas
                    if (data.column.index === 4) data.cell.styles.textColor = parseNetMarginColor(data.cell.text[0]); // Lucro
                    if (data.column.index === 5) data.cell.styles.textColor = parseNetMarginColor(data.cell.text[0]); // Margem
                }
            }
        });

        doc.save(`L2_Financeiro_${month}.pdf`);
    };

    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold" style={{ color: "#F1F3F6" }}>Relatórios</h1>
                    <p className="text-sm mt-0.5" style={{ color: "#5C6478" }}>Análise detalhada de lucro e despesas</p>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                    <MonthSelector value={month} onChange={setMonth} />

                    <button onClick={exportReport} title="Copiar Resumo" className="flex items-center justify-center w-10 h-10 rounded-lg transition-colors"
                        style={{
                            background: "#1A1D26",
                            color: copied ? "#34D399" : "#9CA3B4",
                            border: copied ? "1px solid rgba(52,211,153,0.3)" : "1px solid #2E3340"
                        }}>
                        {copied ? <CheckCircle2 className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                    </button>

                    <button onClick={downloadPDF} className="flex items-center gap-2 px-4 py-2 btn-primary rounded-lg font-medium text-sm transition-colors">
                        <FileDown className="w-4 h-4" /> Baixar PDF
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard title="Faturamento Bruto" value={formatCurrency(totalRevenue)} icon={DollarSign} accentColor="cyan" />
                <StatCard title="Despesas Totais" value={formatCurrency(totalExpenses)} icon={TrendingDown} accentColor="red" />
                <StatCard title="Lucro Líquido" value={formatCurrency(profit)} icon={TrendingUp}
                    accentColor={profit >= 0 ? "violet" : "red"} trend={{ value: `${margin}% margem`, positive: profit >= 0 }} />
                <StatCard title="Clientes" value={String(activeClients.length)} icon={Users} accentColor="cyan" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <div className="l2-border rounded-xl p-7" style={{ background: "#1A1D26" }}>
                    <h2 className="text-xs font-semibold mb-4 uppercase tracking-wider flex items-center gap-2" style={{ color: "#9CA3B4" }}>
                        <Users className="w-4 h-4" style={{ color: "#6366F1" }} /> Lucro por Cliente
                    </h2>
                    {clientProfitability.length === 0 ? (
                        <p className="text-sm text-center py-6" style={{ color: "#5C6478" }}>Nenhum cliente ativo</p>
                    ) : (
                        <div className="space-y-3">
                            {clientProfitability.map((cp) => (
                                <div key={cp.id} className="rounded-lg p-4" style={{ background: "#1F2230", border: "1px solid #2E3340" }}>
                                    <div className="flex items-start justify-between mb-2">
                                        <p className="text-sm font-semibold" style={{ color: "#F1F3F6" }}>{cp.name}</p>
                                        <p className="text-sm font-bold font-mono" style={{ color: cp.profit >= 0 ? "#34D399" : "#F87171" }}>{formatCurrency(cp.profit)}</p>
                                    </div>
                                    <div className="flex items-center gap-4 text-[10px] font-mono uppercase tracking-wider" style={{ color: "#9CA3B4" }}>
                                        <span>Rec: {formatCurrency(cp.revenue)}</span>
                                        <span>Desp: <span style={{ color: "#F87171" }}>{formatCurrency(cp.expenses)}</span></span>
                                        <span style={{ color: parseFloat(cp.margin) >= 50 ? "#34D399" : parseFloat(cp.margin) >= 20 ? "#FBBF24" : "#F87171" }}>{cp.margin}%</span>
                                    </div>
                                    <div className="mt-2 h-1 rounded-full overflow-hidden" style={{ background: "#252937" }}>
                                        <div className={`h-full rounded-full`}
                                            style={{ background: cp.profit >= 0 ? "#34D399" : "#F87171", width: `${Math.min(Math.abs(parseFloat(cp.margin)), 100)}%` }} />
                                    </div>
                                </div>
                            ))}
                            {generalExpenses > 0 && (
                                <div className="rounded-lg p-4" style={{ background: "#1F2230", border: "1px solid #2E3340" }}>
                                    <div className="flex items-center justify-between">
                                        <p className="text-sm font-semibold" style={{ color: "#F1F3F6" }}>Despesas Gerais L2</p>
                                        <p className="text-sm font-bold font-mono" style={{ color: "#F87171" }}>-{formatCurrency(generalExpenses)}</p>
                                    </div>
                                    <p className="text-[10px] mt-1 uppercase tracking-wider" style={{ color: "#5C6478" }}>Gastos não vinculados a cliente</p>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                <div className="l2-border rounded-xl p-7" style={{ background: "#1A1D26" }}>
                    <h2 className="text-xs font-semibold mb-4 uppercase tracking-wider flex items-center gap-2" style={{ color: "#9CA3B4" }}>
                        <BarChart3 className="w-4 h-4" style={{ color: "#6366F1" }} /> Despesas por Categoria
                    </h2>
                    {categoryBreakdown.length === 0 ? (
                        <p className="text-sm text-center py-6" style={{ color: "#5C6478" }}>Nenhuma despesa neste período</p>
                    ) : (
                        <div className="space-y-4">
                            {categoryBreakdown.map((cat) => (
                                <div key={cat.category}>
                                    <div className="flex items-center justify-between mb-1.5">
                                        <span className="text-sm font-medium" style={{ color: "#F1F3F6" }}>{cat.category}</span>
                                        <div className="flex items-center gap-2">
                                            <span className="text-[10px] font-mono" style={{ color: "#5C6478" }}>{cat.percentage}%</span>
                                            <span className="text-sm font-semibold font-mono" style={{ color: "#F87171" }}>{formatCurrency(cat.amount)}</span>
                                        </div>
                                    </div>
                                    <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "#252937" }}>
                                        <div className={`h-full rounded-full animate-grow-up ${barClass[cat.category] || "bar-outros"}`}
                                            style={{ width: `${cat.percentage}%` }} />
                                    </div>
                                </div>
                            ))}
                            <div className="pt-3 mt-3" style={{ borderTop: "1px solid #2E3340" }}>
                                <div className="flex items-center justify-between">
                                    <span className="text-sm font-semibold" style={{ color: "#F1F3F6" }}>Total</span>
                                    <span className="text-base font-bold font-mono" style={{ color: "#F87171" }}>{formatCurrency(totalExpenses)}</span>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* Top Clientes (Faturamento) */}
                <div className="l2-border rounded-xl p-7" style={{ background: "#1A1D26" }}>
                    <h2 className="text-xs font-semibold mb-5 uppercase tracking-wider flex items-center gap-2" style={{ color: "#9CA3B4" }}>
                        <TrendingUp style={{ width: 16, height: 16, color: "#34D399" }} /> Top 5 Clientes (Receita)
                    </h2>
                    {activeClients.length === 0 ? (
                        <p className="text-sm text-center py-6" style={{ color: "#5C6478" }}>Nenhum cliente ativo</p>
                    ) : (
                        <div className="space-y-3">
                            {[...activeClients]
                                .sort((a, b) => b.monthlyPayment - a.monthlyPayment)
                                .slice(0, 5)
                                .map((client, index) => {
                                    return (
                                        <div key={client.id} style={{
                                            padding: 16, borderRadius: 10,
                                            background: index === 0 ? "rgba(99,102,241,0.05)" : "#1F2230",
                                            border: index === 0 ? "1px solid rgba(99,102,241,0.2)" : "1px solid #2E3340",
                                            display: "flex", alignItems: "center", justifyContent: "space-between"
                                        }}>
                                            <div className="flex items-center gap-4">
                                                <div style={{
                                                    width: 28, height: 28, borderRadius: "50%",
                                                    background: index === 0 ? "rgba(99,102,241,0.15)" : "#252937",
                                                    color: index === 0 ? "#6366F1" : "#9CA3B4",
                                                    display: "flex", alignItems: "center", justifyContent: "center",
                                                    fontSize: 12, fontWeight: "bold"
                                                }}>
                                                    {index + 1}
                                                </div>
                                                <div>
                                                    <p className="text-sm font-semibold" style={{ color: "#F1F3F6" }}>{client.name}</p>
                                                    <p className="text-[10px] uppercase tracking-wider" style={{ color: "#9CA3B4" }}>{client.service}</p>
                                                </div>
                                            </div>
                                            <div className="text-right">
                                                <span className="text-sm font-bold font-mono" style={{ color: "#F1F3F6" }}>{formatCurrency(client.monthlyPayment)}</span>
                                                <span className="text-[10px] font-mono block" style={{ color: "#5C6478" }}>{(totalRevenue > 0 ? (client.monthlyPayment / totalRevenue) * 100 : 0).toFixed(1)}%</span>
                                            </div>
                                        </div>
                                    );
                                })}
                        </div>
                    )}
                </div>
            </div>

            {/* ROI por Cliente */}
            <div className="l2-border rounded-xl p-7" style={{ background: "#1A1D26" }}>
                <h2 className="text-xs font-semibold mb-5 uppercase tracking-wider flex items-center gap-2" style={{ color: "#9CA3B4" }}>
                    <DollarSign style={{ width: 16, height: 16, color: "#34D399" }} /> ROI por Cliente
                </h2>
                <p className="text-sm mb-6" style={{ color: "#9CA3B4" }}>
                    Análise de rentabilidade considerando a receita do cliente subtraída de suas despesas específicas neste mês.
                </p>
                {activeClients.length === 0 ? (
                    <p className="text-sm text-center py-6" style={{ color: "#5C6478" }}>Nenhum cliente ativo</p>
                ) : (
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 16 }}>
                        {activeClients.map((client) => {
                            const clientExpenses = monthExpenses.filter(e => e.clientId === client.id).reduce((s, e) => s + e.amount, 0);
                            const profit = client.monthlyPayment - clientExpenses;
                            const roi = clientExpenses > 0 ? ((profit / clientExpenses) * 100).toFixed(0) : "∞";
                            const margin = client.monthlyPayment > 0 ? ((profit / client.monthlyPayment) * 100).toFixed(1) : "0";
                            const isPositive = profit >= 0;

                            return (
                                <div key={client.id} style={{
                                    padding: 20, borderRadius: 12,
                                    background: "#1F2230", border: "1px solid #2E3340",
                                }}>
                                    <div className="flex justify-between items-start mb-4">
                                        <div>
                                            <h3 className="text-sm font-bold" style={{ color: "#F1F3F6" }}>{client.name}</h3>
                                            <span className="text-[10px] px-2 py-0.5 rounded-full mt-1 inline-block"
                                                style={{ background: "rgba(99,102,241,0.1)", color: "#6366F1", border: "1px solid rgba(99,102,241,0.2)" }}>
                                                {client.service}
                                            </span>
                                        </div>
                                        <div className="text-right">
                                            <p className="text-sm font-bold font-mono" style={{ color: isPositive ? "#34D399" : "#F87171" }}>
                                                {formatCurrency(profit)}
                                            </p>
                                            <p className="text-[10px] uppercase tracking-wider" style={{ color: "#9CA3B4" }}>Lucro Líquido</p>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 gap-4 mb-4">
                                        <div className="p-3 rounded-lg" style={{ background: "#252937", border: "1px solid #2E3340" }}>
                                            <p className="text-[10px] uppercase tracking-wider mb-1" style={{ color: "#9CA3B4" }}>Receita</p>
                                            <p className="text-sm font-mono" style={{ color: "#F1F3F6" }}>{formatCurrency(client.monthlyPayment)}</p>
                                        </div>
                                        <div className="p-3 rounded-lg" style={{ background: "#252937", border: "1px solid #2E3340" }}>
                                            <p className="text-[10px] uppercase tracking-wider mb-1" style={{ color: "#9CA3B4" }}>Custos</p>
                                            <p className="text-sm font-mono" style={{ color: "#F87171" }}>{formatCurrency(clientExpenses)}</p>
                                        </div>
                                    </div>

                                    <div className="flex items-center justify-between pt-3" style={{ borderTop: "1px solid #2E3340" }}>
                                        <div className="flex items-center gap-2">
                                            <span className="text-[10px] uppercase tracking-wider" style={{ color: "#9CA3B4" }}>Margem</span>
                                            <span className="text-xs font-bold font-mono" style={{ color: isPositive ? "#34D399" : "#F87171" }}>
                                                {margin}%
                                            </span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-[10px] uppercase tracking-wider" style={{ color: "#9CA3B4" }}>ROI</span>
                                            <span className="text-xs font-bold font-mono" style={{ color: isPositive ? "#34D399" : "#F87171" }}>
                                                {roi === "∞" ? "100%+" : `${roi}%`}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Margem por Serviço */}
            <div className="l2-border rounded-xl p-7" style={{ background: "#1A1D26" }}>
                <h2 className="text-xs font-semibold mb-5 uppercase tracking-wider flex items-center gap-2" style={{ color: "#9CA3B4" }}>
                    <Briefcase style={{ width: 16, height: 16, color: "#6366F1" }} /> Margem por Serviço
                </h2>
                {serviceMargin.length === 0 ? (
                    <p className="text-sm text-center py-6" style={{ color: "#5C6478" }}>Nenhum serviço encontrado</p>
                ) : (
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
                        {serviceMargin.map((s) => {
                            const marginNum = parseFloat(s.margin);
                            const barColor = marginNum >= 60 ? "#34D399" : marginNum >= 30 ? "#FBBF24" : "#F87171";
                            return (
                                <div key={s.service} style={{
                                    padding: 20, borderRadius: 10,
                                    background: "#1F2230", border: "1px solid #2E3340",
                                }}>
                                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
                                        <div>
                                            <p className="text-sm font-semibold" style={{ color: "#F1F3F6" }}>{s.service}</p>
                                            <p className="text-[10px] mt-1 font-mono uppercase tracking-wider" style={{ color: "#5C6478" }}>
                                                {s.count} cliente{s.count > 1 ? "s" : ""}
                                            </p>
                                        </div>
                                        <span className="text-sm font-bold font-mono" style={{ color: barColor }}>
                                            {s.margin}%
                                        </span>
                                    </div>
                                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
                                        <span className="text-[10px] font-mono" style={{ color: "#9CA3B4" }}>Rec: {formatCurrency(s.revenue)}</span>
                                        <span className="text-[10px] font-mono" style={{ color: "#9CA3B4" }}>Desp: {formatCurrency(s.expenses)}</span>
                                    </div>
                                    <div style={{ height: 6, background: "#252937", borderRadius: 3, overflow: "hidden" }}>
                                        <div style={{
                                            height: "100%", borderRadius: 3,
                                            width: `${Math.min(Math.abs(marginNum), 100)}%`,
                                            background: barColor,
                                            transition: "width 600ms cubic-bezier(0.22, 1, 0.36, 1)",
                                        }} />
                                    </div>
                                    <div style={{ marginTop: 8, textAlign: "right" }}>
                                        <span className="text-sm font-bold font-mono" style={{ color: s.profit >= 0 ? "#34D399" : "#F87171" }}>
                                            {formatCurrency(s.profit)}
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}
