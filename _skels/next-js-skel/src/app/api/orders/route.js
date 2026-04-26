import { NextResponse } from 'next/server';
import { getDb } from '../../../lib/db';
import { authenticateRequest } from '../../../lib/auth';

/**
 * GET /api/orders
 * Returns 200 with array of orders belonging to the authenticated user.
 * Requires Bearer auth.
 */
export async function GET(request) {
  let user;
  try {
    user = await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const userId = user.sub ? Number(user.sub) : null;
  const db = getDb();
  const rows = db.prepare('SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC').all(userId);
  return NextResponse.json(rows);
}

/**
 * POST /api/orders
 * Creates a new draft order for the authenticated user.
 * Returns 201 with the created order. Requires Bearer auth.
 */
export async function POST(request) {
  let user;
  try {
    user = await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const userId = user.sub ? Number(user.sub) : null;
  const db = getDb();

  const stmt = db.prepare('INSERT INTO orders (user_id, status) VALUES (?, ?)');
  const result = stmt.run(userId, 'draft');

  const created = db.prepare('SELECT * FROM orders WHERE id = ?').get(result.lastInsertRowid);

  return NextResponse.json(created, { status: 201 });
}
