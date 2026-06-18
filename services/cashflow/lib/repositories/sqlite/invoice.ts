/**
 * Invoice Repository — local SQLite implementation (better-sqlite3).
 */
import db from '../../db';
import type { Invoice, InvoiceStatus } from '../../types';
import type { IInvoiceRepository } from '../types';

function rowToInvoice(row: any): Invoice {
  return {
    id: row.id,
    clientId: row.clientId,
    clientName: row.clientName,
    description: row.description,
    amount: Number(row.amount),
    issueDate: row.issueDate,
    dueDate: row.dueDate,
    paidDate: row.paidDate ?? null,
    status: row.status as InvoiceStatus,
  };
}

function invoiceParams(d: Invoice) {
  return {
    id: d.id,
    clientId: d.clientId,
    clientName: d.clientName,
    description: d.description,
    amount: isNaN(Number(d.amount)) ? 0 : Number(d.amount),
    issueDate: d.issueDate,
    dueDate: d.dueDate,
    paidDate: d.paidDate ?? null,
    status: d.status,
  };
}

function today(): string {
  return new Date().toISOString().split('T')[0];
}

export class SqliteInvoiceRepository implements IInvoiceRepository {
  async getAll(): Promise<Invoice[]> {
    return (db.prepare('SELECT * FROM Invoice ORDER BY issueDate DESC').all() as any[]).map(rowToInvoice);
  }

  async getById(id: string): Promise<Invoice | null> {
    const row = db.prepare('SELECT * FROM Invoice WHERE id = ?').get(id);
    return row ? rowToInvoice(row) : null;
  }

  async getByStatus(status: string): Promise<Invoice[]> {
    return (db.prepare('SELECT * FROM Invoice WHERE status = ? ORDER BY issueDate DESC').all(status) as any[]).map(rowToInvoice);
  }

  async getOverdue(): Promise<Invoice[]> {
    return (db
      .prepare("SELECT * FROM Invoice WHERE status = 'pendente' AND dueDate < ? ORDER BY dueDate ASC")
      .all(today()) as any[]).map(rowToInvoice);
  }

  async create(data: Invoice): Promise<Invoice> {
    db
      .prepare(
        `INSERT OR REPLACE INTO Invoice
          (id, clientId, clientName, description, amount, issueDate, dueDate, status, paidDate, updatedAt)
         VALUES
          (@id, @clientId, @clientName, @description, @amount, @issueDate, @dueDate, @status, @paidDate, CURRENT_TIMESTAMP)`
      )
      .run(invoiceParams(data));
    return data;
  }

  async update(data: Invoice): Promise<Invoice> {
    db
      .prepare(
        `UPDATE Invoice SET
           clientId=@clientId, clientName=@clientName, description=@description, amount=@amount,
           issueDate=@issueDate, dueDate=@dueDate, status=@status, paidDate=@paidDate, updatedAt=CURRENT_TIMESTAMP
         WHERE id=@id`
      )
      .run(invoiceParams(data));
    return data;
  }

  async delete(id: string): Promise<void> {
    db.prepare('DELETE FROM Invoice WHERE id = ?').run(id);
  }
}
