import { NextResponse } from 'next/server';
import { getDb } from '../../../../../../lib/db';
import { authenticateRequest } from '../../../../../../lib/auth';

/**
 * DELETE /api/orders/[id]/lines/[lineId]
 * Removes a line from a draft order. Returns 204 on success.
 * Requires Bearer auth.
 */
export async function DELETE(request, { params }) {
  let user;
  try {
    user = await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { id, lineId } = await params;
  const userId = user.sub ? Number(user.sub) : null;
  const db = getDb();

  const order = db.prepare('SELECT * FROM orders WHERE id = ? AND user_id = ?').get(Number(id), userId);
  if (!order) {
    return NextResponse.json({ error: 'Order not found' }, { status: 404 });
  }

  if (order.status !== 'draft') {
    return NextResponse.json({ error: 'Can only remove lines from draft orders' }, { status: 400 });
  }

  const line = db.prepare('SELECT * FROM order_lines WHERE id = ? AND order_id = ?').get(Number(lineId), Number(id));
  if (!line) {
    return NextResponse.json({ error: 'Order line not found' }, { status: 404 });
  }

  db.prepare('DELETE FROM order_lines WHERE id = ?').run(Number(lineId));
  return new NextResponse(null, { status: 204 });
}
