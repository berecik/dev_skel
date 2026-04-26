import { NextResponse } from 'next/server';
import { getDb } from '../../../../../lib/db';
import { authenticateRequest } from '../../../../../lib/auth';

/**
 * PUT /api/orders/[id]/address
 * Body: { street, city, zip_code, phone?, notes? }
 * Sets or updates the delivery address on a draft order.
 */
export async function PUT(request, { params }) {
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
    return NextResponse.json({ error: 'Order must be in draft status' }, { status: 400 });
  }

  try {
    const body = await request.json();
    const { street, city, zip_code, phone, notes } = body;

    if (!street || !city || !zip_code) {
      return NextResponse.json({ error: 'street, city, and zip_code are required' }, { status: 400 });
    }

    const existing = db.prepare('SELECT * FROM order_addresses WHERE order_id = ?').get(Number(id));

    if (existing) {
      db.prepare(
        `UPDATE order_addresses
         SET street = ?, city = ?, zip_code = ?, phone = ?, notes = ?
         WHERE order_id = ?`
      ).run(street, city, zip_code, phone || '', notes || '', Number(id));
    } else {
      db.prepare(
        `INSERT INTO order_addresses (order_id, street, city, zip_code, phone, notes)
         VALUES (?, ?, ?, ?, ?, ?)`
      ).run(Number(id), street, city, zip_code, phone || '', notes || '');
    }

    return NextResponse.json({ ok: true });
  } catch (err) {
    if (err instanceof SyntaxError) {
      return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
    }
    console.error('Set order address error:', err);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
