import { NextResponse } from 'next/server';
import { eq, and } from 'drizzle-orm';
import { getDb } from '../../../../../lib/db';
import { authenticateRequest } from '../../../../../lib/auth';
import { orders, orderLines, catalogItems } from '../../../../../lib/schema';

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
  const orderId = Number(id);
  const userId = user.sub ? Number(user.sub) : null;
  const db = getDb();

  const order = db
    .select()
    .from(orders)
    .where(and(eq(orders.id, orderId), eq(orders.user_id, userId)))
    .get();
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

    const catalogItem = db
      .select()
      .from(catalogItems)
      .where(eq(catalogItems.id, Number(catalog_item_id)))
      .get();
    if (!catalogItem) {
      return NextResponse.json({ error: 'Catalog item not found' }, { status: 404 });
    }

    const unitPrice = catalogItem.price || 0.0;
    const lineQuantity = quantity || 1;

    const created = db
      .insert(orderLines)
      .values({
        order_id: orderId,
        catalog_item_id: Number(catalog_item_id),
        quantity: lineQuantity,
        unit_price: unitPrice,
      })
      .returning()
      .get();

    return NextResponse.json(created, { status: 201 });
  } catch (err) {
    if (err instanceof SyntaxError) {
      return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
    }
    console.error('Add order line error:', err);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
