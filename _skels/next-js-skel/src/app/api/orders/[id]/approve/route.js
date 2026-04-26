import { NextResponse } from 'next/server';
import { getDb } from '../../../../../lib/db';
import { authenticateRequest } from '../../../../../lib/auth';

/**
 * POST /api/orders/[id]/approve
 * Body: { wait_minutes?, feedback? }
 * Transitions a pending order to approved status.
 * Returns 200 with the updated order. Requires Bearer auth.
 */
export async function POST(request, { params }) {
  try {
    await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { id } = await params;
  const db = getDb();

  const order = db.prepare('SELECT * FROM orders WHERE id = ?').get(Number(id));
  if (!order) {
    return NextResponse.json({ error: 'Order not found' }, { status: 404 });
  }

  if (order.status !== 'pending') {
    return NextResponse.json({ error: 'Only pending orders can be approved' }, { status: 400 });
  }

  try {
    const body = await request.json();
    const { wait_minutes, feedback } = body;

    db.prepare(
      'UPDATE orders SET status = ?, wait_minutes = ?, feedback = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?'
    ).run('approved', wait_minutes ?? null, feedback || null, Number(id));

    const updated = db.prepare('SELECT * FROM orders WHERE id = ?').get(Number(id));
    return NextResponse.json(updated);
  } catch (err) {
    if (err instanceof SyntaxError) {
      return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
    }
    console.error('Approve order error:', err);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
