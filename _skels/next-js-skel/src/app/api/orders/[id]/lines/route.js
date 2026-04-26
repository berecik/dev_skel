import { NextResponse } from 'next/server';
import { getDb } from '../../../../../lib/db';
import { authenticateRequest } from '../../../../../lib/auth';

/**
 * POST /api/orders/[id]/lines
 * Body: { catalog_item_id, quantity? }
 * Adds a line to a draft order. Looks up unit_price from catalog.
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
    return NextResponse.json({ error: 'Can only add lines to draft orders' }, { status: 400 });
  }

  try {
    const body = await request.json();
    const { catalog_item_id, quantity } = body;

    if (!catalog_item_id) {
      return NextResponse.json({ error: 'catalog_item_id is required' }, { status: 400 });
    }

    const catalogItem = db.prepare('SELECT * FROM catalog_items WHERE id = ?').get(Number(catalog_item_id));
    if (!catalogItem) {
      return NextResponse.json({ error: 'Catalog item not found' }, { status: 404 });
    }

    const unitPrice = catalogItem.price || 0.0;
    const lineQuantity = quantity || 1;

    const stmt = db.prepare(
      'INSERT INTO order_lines (order_id, catalog_item_id, quantity, unit_price) VALUES (?, ?, ?, ?)'
    );
    const result = stmt.run(Number(id), Number(catalog_item_id), lineQuantity, unitPrice);

    const created = db.prepare('SELECT * FROM order_lines WHERE id = ?').get(result.lastInsertRowid);
    return NextResponse.json(created, { status: 201 });
  } catch (err) {
    if (err instanceof SyntaxError) {
      return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
    }
    console.error('Add order line error:', err);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
