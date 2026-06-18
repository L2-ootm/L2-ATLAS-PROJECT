// L2 Financeiro — Tax calculations (MEI)

// DAS MEI fixo (2024/2025 — serviços)
const DAS_MEI_MENSAL = 71.60;
const LIMITE_ANUAL_MEI = 81000;

export interface TaxEstimate {
    dasMonthly: number;
    annualRevenue: number;
    annualLimit: number;
    percentUsed: number;
    remaining: number;
    alert: "ok" | "warning" | "danger";
}

export function calculateMEITax(monthlyRevenue: number, currentMonth: number): TaxEstimate {
    const annualRevenue = monthlyRevenue * 12;
    const accumulatedRevenue = monthlyRevenue * currentMonth;
    const percentUsed = (accumulatedRevenue / LIMITE_ANUAL_MEI) * 100;
    const remaining = LIMITE_ANUAL_MEI - accumulatedRevenue;

    let alert: TaxEstimate["alert"] = "ok";
    if (percentUsed >= 90) alert = "danger";
    else if (percentUsed >= 70) alert = "warning";

    return {
        dasMonthly: DAS_MEI_MENSAL,
        annualRevenue,
        annualLimit: LIMITE_ANUAL_MEI,
        percentUsed: Math.min(percentUsed, 100),
        remaining: Math.max(remaining, 0),
        alert,
    };
}

export function getDASValue(): number {
    return DAS_MEI_MENSAL;
}
