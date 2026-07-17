/**
 * Partner Repository — local SQLite implementation (better-sqlite3).
 */
import db from '../../db';
import type { PartnerWallet, PartnerTransaction } from '../../types';
import type { IPartnerRepository } from '../types';

function rowToWallet(row: any): PartnerWallet {
  return { id: row.id, name: row.name, balance: Number(row.balance) };
}

function rowToTransaction(row: any): PartnerTransaction {
  return {
    id: row.id,
    partnerId: row.partnerId,
    type: row.type,
    amount: Number(row.amount),
    date: row.date,
    description: row.description,
  };
}

export class SqlitePartnerRepository implements IPartnerRepository {
  private ensureDefaults(): void {
    const count = (db.prepare('SELECT COUNT(*) AS n FROM Partner').get() as any).n as number;
    if (count === 0) {
      const ins = db.prepare('INSERT INTO Partner (id, name, role, balance) VALUES (?, ?, ?, 0)');
      ins.run('partner-a', 'Partner A', 'partner');
      ins.run('partner-b', 'Partner B', 'partner');
    }
  }

  async getWallets(): Promise<PartnerWallet[]> {
    this.ensureDefaults();
    return (db.prepare('SELECT * FROM Partner').all() as any[]).map(rowToWallet);
  }

  async getWalletById(id: string): Promise<PartnerWallet | null> {
    const row = db.prepare('SELECT * FROM Partner WHERE id = ?').get(id);
    return row ? rowToWallet(row) : null;
  }

  async updateWalletBalance(walletId: string, amountChange: number): Promise<void> {
    db.prepare('UPDATE Partner SET balance = balance + ? WHERE id = ?').run(amountChange, walletId);
  }

  async getTransactions(): Promise<PartnerTransaction[]> {
    return (db.prepare('SELECT * FROM PartnerTransaction ORDER BY date DESC').all() as any[]).map(rowToTransaction);
  }

  async addTransaction(data: PartnerTransaction): Promise<PartnerTransaction> {
    const amount = isNaN(Number(data.amount)) ? 0 : Number(data.amount);
    const apply = db.transaction((d: PartnerTransaction) => {
      db.prepare(
        `INSERT OR REPLACE INTO PartnerTransaction
          (id, partnerId, type, amount, description, date)
         VALUES (@id, @partnerId, @type, @amount, @description, @date)`
      ).run({
        id: d.id,
        partnerId: d.partnerId,
        type: d.type,
        amount,
        description: d.description,
        date: d.date,
      });
      // Apply the wallet balance change (injection +, withdrawal -, adjustment signed).
      const delta = d.type === 'withdrawal' ? -Math.abs(amount) : amount;
      db.prepare('UPDATE Partner SET balance = balance + ? WHERE id = ?').run(delta, d.partnerId);
    });
    apply(data);
    return data;
  }
}
