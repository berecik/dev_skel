import { NextResponse } from 'next/server';
import { eq, and, asc } from 'drizzle-orm';
import { getDb } from '../../../../lib/db';
import { authenticateRequest } from '../../../../lib/auth';
import { orders, orderLines, orderAddresses } from '../../../../lib/schema';

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

  const lines = db
    .select({
      id: orderLines.id,
      catalog_item_id: orderLines.catalog_item_id,
      quantity: orderLines.quantity,
      unit_price: orderLines.unit_price,
    })
    .from(orderLines)
    .where(eq(orderLines.order_id, orderId))
    .orderBy(asc(orderLines.id))
    .all();

  const address =
    db.select().from(orderAddresses).where(eq(orderAddresses.order_id, orderId)).get() || null;

  return NextResponse.json({ ...order, lines, address });
}
