/**
 * Expense Repository — local SQLite implementation (better-sqlite3).
 */
import db from '../../db';
import type { Expense, ExpenseCategory } from '../../types';
import type { IExpenseRepository } from '../types';

function rowToExpense(row: any): Expense {
  return {
    id: row.id,
    clientId: row.clientId ?? null,
    category: row.category as ExpenseCategory,
    description: row.description,
    amount: Number(row.amount),
    date: row.date,
    recurring: row.recurring === 1 || row.recurring === true,
  };
}

function expenseParams(d: Expense) {
  return {
    id: d.id,
    clientId: d.clientId ?? null,
    category: d.category,
    description: d.description,
    amount: isNaN(Number(d.amount)) ? 0 : Number(d.amount),
    date: d.date,
    recurring: d.recurring ? 1 : 0,
  };
}

export class SqliteExpenseRepository implements IExpenseRepository {
  async getAll(): Promise<Expense[]> {
    return (db.prepare('SELECT * FROM Expense ORDER BY date DESC').all() as any[]).map(rowToExpense);
  }

  async getById(id: string): Promise<Expense | null> {
    const row = db.prepare('SELECT * FROM Expense WHERE id = ?').get(id);
    return row ? rowToExpense(row) : null;
  }

  async getByMonth(monthYear: string): Promise<Expense[]> {
    return (db.prepare('SELECT * FROM Expense WHERE date LIKE ? ORDER BY date DESC').all(`${monthYear}%`) as any[]).map(rowToExpense);
  }

  async getByClient(clientId: string): Promise<Expense[]> {
    return (db.prepare('SELECT * FROM Expense WHERE clientId = ? ORDER BY date DESC').all(clientId) as any[]).map(rowToExpense);
  }

  async create(data: Expense): Promise<Expense> {
    db
      .prepare(
        `INSERT OR REPLACE INTO Expense
          (id, clientId, category, description, amount, date, recurring, updatedAt)
         VALUES
          (@id, @clientId, @category, @description, @amount, @date, @recurring, CURRENT_TIMESTAMP)`
      )
      .run(expenseParams(data));
    return data;
  }

  async update(data: Expense): Promise<Expense> {
    db
      .prepare(
        `UPDATE Expense SET
           clientId=@clientId, category=@category, description=@description, amount=@amount,
           date=@date, recurring=@recurring, updatedAt=CURRENT_TIMESTAMP
         WHERE id=@id`
      )
      .run(expenseParams(data));
    return data;
  }

  async delete(id: string): Promise<void> {
    db.prepare('DELETE FROM Expense WHERE id = ?').run(id);
  }
}
