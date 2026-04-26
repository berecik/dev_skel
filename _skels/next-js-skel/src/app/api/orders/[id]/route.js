import { NextResponse } from 'next/server';
import { getDb } from '../../../../lib/db';
import { authenticateRequest } from '../../../../lib/auth';

/**
 * GET /api/orders/[id]
 * Returns 200 with the order detail including lines and address, or 404.
 * Only returns the order if it belongs to the authenticated user.
 * Requires Bearer auth.
 */
export async function GET(request, { params }) {
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

  const lines = db.prepare(
    `SELECT ol.id, ol.catalog_item_id, ol.quantity, ol.unit_price
     FROM order_lines ol
     WHERE ol.order_id = ?
     ORDER BY ol.id`
  ).all(Number(id));

  const address = db.prepare('SELECT * FROM order_addresses WHERE order_id = ?').get(Number(id)) || null;

  return NextResponse.json({ ...order, lines, address });
}
