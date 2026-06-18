/**
 * Client Repository — local SQLite implementation (better-sqlite3).
 */
import db from '../../db';
import type { Client } from '../../types';
import type { IClientRepository } from '../types';

function rowToClient(row: any): Client {
  return {
    id: row.id,
    name: row.name,
    service: row.service,
    monthlyPayment: Number(row.monthlyPayment),
    startDate: row.startDate,
    contractMonths: row.contractMonths ?? 0,
    active: row.active === 1 || row.active === true,
    notes: row.notes ?? '',
    phone: row.phone ?? undefined,
  };
}

function clientParams(d: Client) {
  return {
    id: d.id,
    name: d.name,
    service: d.service,
    monthlyPayment: isNaN(Number(d.monthlyPayment)) ? 0 : Number(d.monthlyPayment),
    startDate: d.startDate,
    contractMonths: typeof d.contractMonths === 'number' ? d.contractMonths : 0,
    active: d.active ? 1 : 0,
    phone: d.phone ?? null,
    notes: d.notes ?? null,
  };
}

export class SqliteClientRepository implements IClientRepository {
  async getAll(): Promise<Client[]> {
    return (db.prepare('SELECT * FROM Client ORDER BY createdAt DESC').all() as any[]).map(rowToClient);
  }

  async getActive(): Promise<Client[]> {
    return (db.prepare('SELECT * FROM Client WHERE active = 1 ORDER BY createdAt DESC').all() as any[]).map(rowToClient);
  }

  async getById(id: string): Promise<Client | null> {
    const row = db.prepare('SELECT * FROM Client WHERE id = ?').get(id);
    return row ? rowToClient(row) : null;
  }

  async create(data: Client): Promise<Client> {
    db
      .prepare(
        `INSERT OR REPLACE INTO Client
          (id, name, service, monthlyPayment, startDate, contractMonths, active, phone, notes, updatedAt)
         VALUES
          (@id, @name, @service, @monthlyPayment, @startDate, @contractMonths, @active, @phone, @notes, CURRENT_TIMESTAMP)`
      )
      .run(clientParams(data));
    return data;
  }

  async update(data: Client): Promise<Client> {
    db
      .prepare(
        `UPDATE Client SET
           name=@name, service=@service, monthlyPayment=@monthlyPayment, startDate=@startDate,
           contractMonths=@contractMonths, active=@active, phone=@phone, notes=@notes, updatedAt=CURRENT_TIMESTAMP
         WHERE id=@id`
      )
      .run(clientParams(data));
    return data;
  }

  async delete(id: string): Promise<void> {
    db.prepare('DELETE FROM Client WHERE id = ?').run(id);
  }
}
