// L2 Financeiro — Cash flow & revenue forecast

import { Client, Expense } from "./types";

export interface MonthProjection {
    month: string;          // "2026-03"
    label: string;          // "Mar"
    revenue: number;
    recurringExpenses: number;
    estimatedProfit: number;
    cumulativeBalance: number;
}

export interface ForecastSummary {
    projections: MonthProjection[];
    total3Months: number;
    total6Months: number;
    avgMonthlyProfit: number;
    annualProjection: number;
}

const MONTH_LABELS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];

export function generateCashFlowProjection(
    activeClients: Client[],
    expenses: Expense[],
    startMonth: string,
    months: number = 6
): ForecastSummary {
    const monthlyRevenue = activeClients.reduce((sum, c) => sum + c.monthlyPayment, 0);
    const recurringExpenses = expenses.filter((e) => e.recurring);

    // Average recurring monthly expense
    const recurringTotal = recurringExpenses.reduce((sum, e) => sum + e.amount, 0);
    // Use unique months to calculate average
    const uniqueMonths = new Set(recurringExpenses.map((e) => e.date.substring(0, 7)));
    const avgRecurring = uniqueMonths.size > 0 ? recurringTotal / uniqueMonths.size : 0;

    const projections: MonthProjection[] = [];
    let cumulativeBalance = 0;

    const [startYear, startMon] = startMonth.split("-").map(Number);

    for (let i = 0; i < months; i++) {
        let m = startMon + i;
        let y = startYear;
        while (m > 12) {
            m -= 12;
            y++;
        }

        const monthStr = `${y}-${String(m).padStart(2, "0")}`;
        const estimatedProfit = monthlyRevenue - avgRecurring;
        cumulativeBalance += estimatedProfit;

        projections.push({
            month: monthStr,
            label: MONTH_LABELS[m - 1],
            revenue: monthlyRevenue,
            recurringExpenses: avgRecurring,
            estimatedProfit,
            cumulativeBalance,
        });
    }

    const total3 = projections.slice(0, 3).reduce((s, p) => s + p.estimatedProfit, 0);
    const total6 = projections.reduce((s, p) => s + p.estimatedProfit, 0);

    return {
        projections,
        total3Months: total3,
        total6Months: total6,
        avgMonthlyProfit: months > 0 ? total6 / months : 0,
        annualProjection: monthlyRevenue * 12,
    };
}

export function getMonthComparison(
    expenses: Expense[],
    activeClients: Client[],
    currentMonth: string,
    numMonths: number = 6
): { month: string; label: string; revenue: number; expenses: number; profit: number }[] {
    const [curYear, curMon] = currentMonth.split("-").map(Number);
    const result = [];

    const monthlyRevenue = activeClients.reduce((sum, c) => sum + c.monthlyPayment, 0);

    for (let i = numMonths - 1; i >= 0; i--) {
        let m = curMon - i;
        let y = curYear;
        while (m <= 0) {
            m += 12;
            y--;
        }
        const monthStr = `${y}-${String(m).padStart(2, "0")}`;
        const monthExp = expenses
            .filter((e) => e.date.startsWith(monthStr))
            .reduce((s, e) => s + e.amount, 0);

        result.push({
            month: monthStr,
            label: MONTH_LABELS[m - 1],
            revenue: monthlyRevenue,
            expenses: monthExp,
            profit: monthlyRevenue - monthExp,
        });
    }

    return result;
}
