import db from './index';

export const RBAC_PERMISSIONS = {
  admin: ['*'],
  manager: ['view_dashboard', 'view_reports', 'manage_contracts', 'view_audit'],
  viewer: ['view_dashboard', 'view_reports']
};

export function logAudit(data: {
  id: string;
  user_id?: string;
  user_email?: string;
  action: string;
  entity_type: string;
  entity_id?: string;
  details_json?: string;
  ip_address?: string;
}) {
  const stmt = db.prepare(`
    INSERT INTO audit_log (
      id, user_id, user_email, action, entity_type, entity_id, details_json, ip_address
    ) VALUES (
      @id, @user_id, @user_email, @action, @entity_type, @entity_id, @details_json, @ip_address
    )
  `);

  return stmt.run({
    id: data.id,
    user_id: data.user_id || null,
    user_email: data.user_email || null,
    action: data.action,
    entity_type: data.entity_type,
    entity_id: data.entity_id || null,
    details_json: data.details_json || null,
    ip_address: data.ip_address || null
  });
}

export function getAuditLog(filters?: { action?: string; entity_type?: string; user_email?: string }) {
  let query = 'SELECT * FROM audit_log WHERE 1=1';
  const params: any[] = [];

  if (filters?.action) {
    query += ' AND action = ?';
    params.push(filters.action);
  }
  if (filters?.entity_type) {
    query += ' AND entity_type = ?';
    params.push(filters.entity_type);
  }
  if (filters?.user_email) {
    query += ' AND user_email = ?';
    params.push(filters.user_email);
  }

  query += ' ORDER BY created_at DESC LIMIT 200';

  const stmt = db.prepare(query);
  return stmt.all(...params);
}

export function getSystemUsers() {
  const stmt = db.prepare('SELECT id, email, name, role, active, last_login, created_at FROM system_users ORDER BY name ASC');
  return stmt.all();
}
