export interface Client {
    id: string;
    name: string;
    service: string;
    monthlyPayment: number;
    startDate: string; // Used as contract start date
    contractMonths?: number; // 0 for month-to-month, e.g. 6, 12
    active: boolean;
    notes: string;
    phone?: string;
}

export interface Expense {
    id: string;
    clientId: string | null;
    category: ExpenseCategory;
    description: string;
    amount: number;
    date: string;
    recurring: boolean;
}

export type ExpenseCategory =
    | "Software"
    | "Marketing"
    | "Equipamento"
    | "Infraestrutura"
    | "Pessoal"
    | "Outros";

export const EXPENSE_CATEGORIES: ExpenseCategory[] = [
    "Software",
    "Marketing",
    "Equipamento",
    "Infraestrutura",
    "Pessoal",
    "Outros",
];

export type InvoiceStatus = "pendente" | "pago" | "atrasado";

export interface Invoice {
    id: string;
    clientId: string;
    clientName: string;
    description: string;
    amount: number;
    issueDate: string;
    dueDate: string;
    paidDate: string | null;
    status: InvoiceStatus;
}

export const INVOICE_STATUSES: InvoiceStatus[] = ["pendente", "pago", "atrasado"];

export interface PartnerWallet {
    id: string; // e.g. 'partner-a' | 'partner-b'
    name: string;
    balance: number;
}

export type TransactionType = "injection" | "withdrawal" | "adjustment";

export interface PartnerTransaction {
    id: string;
    partnerId: string; // e.g. 'partner-a' | 'partner-b'
    type: TransactionType;
    amount: number;
    date: string;
    description: string;
}
