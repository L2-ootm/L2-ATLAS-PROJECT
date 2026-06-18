import db from './lib/db/index';
import { generateId } from './lib/utils';
import { logAudit } from './lib/db/audit';

console.log("Injetando dados mockados de Auditoria e Usuários...");

try {
  // Criar usuários
  const usersStmt = db.prepare(`
    INSERT INTO system_users (id, email, name, role, active, last_login)
    VALUES (@id, @email, @name, @role, @active, @last_login)
  `);

  const users = [
    { id: generateId(), email: 'admin@l2.com', name: 'Artur Admin', role: 'admin', active: 1, last_login: new Date().toISOString() },
    { id: generateId(), email: 'manager@l2.com', name: 'João Gerente', role: 'manager', active: 1, last_login: new Date(Date.now() - 86400000).toISOString() },
    { id: generateId(), email: 'viewer@tds.com', name: 'Maria Cliente', role: 'viewer', active: 1, last_login: new Date(Date.now() - 86400000 * 3).toISOString() },
  ];

  for (const u of users) {
    try {
      usersStmt.run(u);
    } catch (e) {
      console.log(`Usuário ${u.email} já existe.`);
    }
  }

  // Criar eventos de auditoria
  const actions = ['create', 'update', 'delete', 'login', 'export'];
  const entities = ['contract', 'client_account', 'plus_subscription', 'report', 'system'];

  for (let i = 0; i < 20; i++) {
    const user = users[Math.floor(Math.random() * users.length)];
    const action = actions[Math.floor(Math.random() * actions.length)];
    const entity = entities[Math.floor(Math.random() * entities.length)];
    
    logAudit({
      id: generateId(),
      user_id: user.id,
      user_email: user.email,
      action,
      entity_type: entity,
      entity_id: generateId(),
      details_json: JSON.stringify({ field: 'status', old: 'pending', new: 'active' }),
      ip_address: `192.168.1.${Math.floor(Math.random() * 255)}`
    });
  }

  console.log("Mock de Auditoria finalizado!");

} catch (error) {
  console.error("Erro ao mockar auditoria:", error);
}
