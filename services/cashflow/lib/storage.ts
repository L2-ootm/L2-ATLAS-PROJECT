import { Client, Expense, Invoice } from "./types";

const CLIENTS_KEY = "l2_financeiro_clients";
const EXPENSES_KEY = "l2_financeiro_expenses";
const INVOICES_KEY = "l2_financeiro_invoices";
const PARTNER_WALLETS_KEY = "l2_financeiro_partner_wallets";
const PARTNER_TRANS_KEY = "l2_financeiro_partner_transactions";

// Clients
export function getClients(): Client[] {
    if (typeof window === "undefined") return [];
    const data = localStorage.getItem(CLIENTS_KEY);
    return data ? JSON.parse(data) : [];
}

export function saveClients(clients: Client[]): void {
    localStorage.setItem(CLIENTS_KEY, JSON.stringify(clients));
}

export function addClient(client: Client): void {
    const clients = getClients();
    if (clients.some(c => c.id === client.id)) return;
    clients.push(client);
    saveClients(clients);
}

export function updateClient(updated: Client): void {
    const clients = getClients().map((c) => (c.id === updated.id ? updated : c));
    saveClients(clients);
}

export function deleteClient(id: string): void {
    const clients = getClients().filter((c) => c.id !== id);
    saveClients(clients);
}

// Expenses
export function getExpenses(): Expense[] {
    if (typeof window === "undefined") return [];
    const data = localStorage.getItem(EXPENSES_KEY);
    return data ? JSON.parse(data) : [];
}

export function saveExpenses(expenses: Expense[]): void {
    localStorage.setItem(EXPENSES_KEY, JSON.stringify(expenses));
}

export function addExpense(expense: Expense): void {
    const expenses = getExpenses();
    if (expenses.some(e => e.id === expense.id)) return;
    expenses.push(expense);
    saveExpenses(expenses);
}

export function updateExpense(updated: Expense): void {
    const expenses = getExpenses().map((e) => (e.id === updated.id ? updated : e));
    saveExpenses(expenses);
}

export function deleteExpense(id: string): void {
    const expenses = getExpenses().filter((e) => e.id !== id);
    saveExpenses(expenses);
}

// Filtered queries
export function getExpensesByMonth(monthYear: string): Expense[] {
    return getExpenses().filter((e) => e.date.startsWith(monthYear));
}

export function getExpensesByClient(clientId: string): Expense[] {
    return getExpenses().filter((e) => e.clientId === clientId);
}

export function getActiveClients(): Client[] {
    return getClients().filter((c) => c.active);
}

// Invoices
export function getInvoices(): Invoice[] {
    if (typeof window === "undefined") return [];
    const data = localStorage.getItem(INVOICES_KEY);
    return data ? JSON.parse(data) : [];
}

export function saveInvoices(invoices: Invoice[]): void {
    localStorage.setItem(INVOICES_KEY, JSON.stringify(invoices));
}

export function addInvoice(invoice: Invoice): void {
    const invoices = getInvoices();
    if (invoices.some(i => i.id === invoice.id)) return;
    invoices.push(invoice);
    saveInvoices(invoices);
}

export function updateInvoice(updated: Invoice): void {
    const invoices = getInvoices().map((i) => (i.id === updated.id ? updated : i));
    saveInvoices(invoices);
}

export function deleteInvoice(id: string): void {
    const invoices = getInvoices().filter((i) => i.id !== id);
    saveInvoices(invoices);
}

export function getInvoicesByStatus(status: string): Invoice[] {
    return getInvoices().filter((i) => i.status === status);
}

export function getOverdueInvoices(): Invoice[] {
    const today = new Date().toISOString().split("T")[0];
    return getInvoices().filter((i) => i.status === "pendente" && i.dueDate < today);
}

export function getInvoicesDueSoon(days: number = 7): Invoice[] {
    const today = new Date();
    const futureDate = new Date(today.getTime() + days * 86400000).toISOString().split("T")[0];
    const todayStr = today.toISOString().split("T")[0];
    return getInvoices().filter((i) => i.status === "pendente" && i.dueDate >= todayStr && i.dueDate <= futureDate);
}

// Partners (Caixa L2 & Sócios)
export function getPartnerWallets(): import("./types").PartnerWallet[] {
    if (typeof window === "undefined") return [];
    const data = localStorage.getItem(PARTNER_WALLETS_KEY);
    if (!data) {
        // Initialize generic partner wallets when none exist.
        const defaultWallets = [
            { id: "partner-a", name: "Partner A", balance: 0 },
            { id: "partner-b", name: "Partner B", balance: 0 }
        ];
        savePartnerWallets(defaultWallets);
        return defaultWallets;
    }
    return JSON.parse(data);
}

export function savePartnerWallets(wallets: import("./types").PartnerWallet[]): void {
    localStorage.setItem(PARTNER_WALLETS_KEY, JSON.stringify(wallets));
}

export function updatePartnerWallet(walletId: string, amountChange: number): void {
    const wallets = getPartnerWallets();
    const updated = wallets.map(w => {
        if (w.id === walletId) {
            return { ...w, balance: w.balance + amountChange };
        }
        return w;
    });
    savePartnerWallets(updated);
}

export function getPartnerTransactions(): import("./types").PartnerTransaction[] {
    if (typeof window === "undefined") return [];
    const data = localStorage.getItem(PARTNER_TRANS_KEY);
    return data ? JSON.parse(data) : [];
}

export function savePartnerTransactions(transactions: import("./types").PartnerTransaction[]): void {
    localStorage.setItem(PARTNER_TRANS_KEY, JSON.stringify(transactions));
}

export function addPartnerTransaction(transaction: import("./types").PartnerTransaction): void {
    const trans = getPartnerTransactions();
    if (trans.some(t => t.id === transaction.id)) return;
    trans.push(transaction);
    savePartnerTransactions(trans);

    // Apply the wallet update
    if (transaction.type === "injection") {
        updatePartnerWallet(transaction.partnerId, transaction.amount);
    } else if (transaction.type === "withdrawal") {
        updatePartnerWallet(transaction.partnerId, -Math.abs(transaction.amount));
    }
}
