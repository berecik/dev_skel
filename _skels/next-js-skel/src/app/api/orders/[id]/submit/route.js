import { NextResponse } from 'next/server';
import { getDb } from '../../../../../lib/db';
import { authenticateRequest } from '../../../../../lib/auth';

/**
 * POST /api/orders/[id]/submit
 * Transitions a draft order to pending status.
 * Returns 200 with the updated order. Requires Bearer auth.
 */
export async function POST(request, { params }) {
  let user;
  try {
    user = await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { id } = await params;
  const userId = user.sub ? Number(user.sub) : null;
  const db = getDb();

  const order = db.prepare('SELECT * FROM orders WHERE id = ? AND user_id = ?').get(Number(id), userId);
  if (!order) {
    return NextResponse.json({ error: 'Order not found' }, { status: 404 });
  }

  if (order.status !== 'draft') {
    return NextResponse.json({ error: 'Only draft orders can be submitted' }, { status: 400 });
  }

  db.prepare('UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?').run('pending', Number(id));

  const updated = db.prepare('SELECT * FROM orders WHERE id = ?').get(Number(id));
  return NextResponse.json(updated);
}
