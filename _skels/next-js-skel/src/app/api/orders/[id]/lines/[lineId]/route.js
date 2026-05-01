import { NextResponse } from 'next/server';
import { eq, and } from 'drizzle-orm';
import { getDb } from '../../../../../../lib/db';
import { authenticateRequest } from '../../../../../../lib/auth';
import { orders, orderLines } from '../../../../../../lib/schema';

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
  const orderId = Number(id);
  const lineIdNum = Number(lineId);
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
    return NextResponse.json(
      { error: 'Can only remove lines from draft orders' },
      { status: 400 },
    );
  }

  const line = db
    .select()
    .from(orderLines)
    .where(and(eq(orderLines.id, lineIdNum), eq(orderLines.order_id, orderId)))
    .get();
  if (!line) {
    return NextResponse.json({ error: 'Order line not found' }, { status: 404 });
  }

  db.delete(orderLines).where(eq(orderLines.id, lineIdNum)).run();
  return new NextResponse(null, { status: 204 });
}
