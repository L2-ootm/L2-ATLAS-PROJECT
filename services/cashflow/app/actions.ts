"use server";

import { clientRepo, expenseRepo, invoiceRepo, partnerRepo } from "@/lib/repositories";
import { revalidatePath } from "next/cache";

/* =========================================================================
   CLIENTS
========================================================================= */

export async function getClients() {
    return await clientRepo.getAll();
}

export async function getActiveClients() {
    return await clientRepo.getActive();
}

export async function addClient(data: any) {
    const newClient = await clientRepo.create(data);
    revalidatePath("/clientes");
    return newClient;
}

export async function updateClient(data: any) {
    const updatedClient = await clientRepo.update(data);
    revalidatePath("/clientes");
    return updatedClient;
}

export async function deleteClient(id: string) {
    await clientRepo.delete(id);
    revalidatePath("/clientes");
}

/* =========================================================================
   EXPENSES
========================================================================= */

export async function getExpenses() {
    return await expenseRepo.getAll();
}

export async function addExpense(data: any) {
    const newExpense = await expenseRepo.create(data);
    revalidatePath("/despesas");
    return newExpense;
}

export async function updateExpense(data: any) {
    const updatedExpense = await expenseRepo.update(data);
    revalidatePath("/despesas");
    return updatedExpense;
}

export async function deleteExpense(id: string) {
    await expenseRepo.delete(id);
    revalidatePath("/despesas");
}

/* =========================================================================
   INVOICES
========================================================================= */

export async function getInvoices() {
    return await invoiceRepo.getAll();
}

export async function addInvoice(data: any) {
    const newInvoice = await invoiceRepo.create(data);
    revalidatePath("/faturas");
    return newInvoice;
}

export async function updateInvoice(data: any) {
    const updatedInvoice = await invoiceRepo.update(data);
    revalidatePath("/faturas");
    return updatedInvoice;
}

export async function deleteInvoice(id: string) {
    await invoiceRepo.delete(id);
    revalidatePath("/faturas");
}

/* =========================================================================
   PARTNERS
========================================================================= */

export async function getPartnerWallets() {
    return await partnerRepo.getWallets();
}

export async function updatePartnerWallet(walletId: string, amountChange: number) {
    await partnerRepo.updateWalletBalance(walletId, amountChange);
}

export async function getPartnerTransactions() {
    return await partnerRepo.getTransactions();
}

export async function addPartnerTransaction(data: any) {
    const newTx = await partnerRepo.addTransaction(data);
    revalidatePath("/socios");

    // updatePartnerWallet is now handled inside addPartnerTransaction via trigger or directly
    // Wait, the sqlite version did:
    // if (data.type === "injection") await updatePartnerWallet(data.partnerId, parsedAmount);
    // Let's replicate this here since Supabase repo doesn't do it automatically

    const parsedAmount = isNaN(parseFloat(data.amount)) ? 0 : parseFloat(data.amount);
    if (data.type === "injection") {
        await partnerRepo.updateWalletBalance(data.partnerId, parsedAmount);
    } else if (data.type === "withdrawal") {
        await partnerRepo.updateWalletBalance(data.partnerId, -Math.abs(parsedAmount));
    }

    return newTx;
}
