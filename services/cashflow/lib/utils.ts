export function formatCurrency(value: number): string {
    return new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL",
    }).format(value);
}

export function formatDate(dateStr: string): string {
    const date = new Date(dateStr + "T00:00:00");
    return date.toLocaleDateString("pt-BR");
}

export function generateId(): string {
    return Date.now().toString(36) + Math.random().toString(36).slice(2);
}

export function getMonthYear(date: Date): string {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

export function getMonthLabel(monthYear: string): string {
    const [year, month] = monthYear.split("-");
    const months = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ];
    return `${months[parseInt(month) - 1]} ${year}`;
}

export function parseMonthYear(monthYear: string): { year: number; month: number } {
    const [year, month] = monthYear.split("-").map(Number);
    return { year, month };
}
