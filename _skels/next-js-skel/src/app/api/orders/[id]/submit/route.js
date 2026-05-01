import { NextResponse } from 'next/server';
import { eq, and } from 'drizzle-orm';
import { getDb } from '../../../../../lib/db';
import { authenticateRequest } from '../../../../../lib/auth';
import { orders } from '../../../../../lib/schema';

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
    return NextResponse.json({ error: 'Only draft orders can be submitted' }, { status: 400 });
  }

  const updated = db
    .update(orders)
    .set({ status: 'pending', updated_at: new Date() })
    .where(eq(orders.id, orderId))
    .returning()
    .get();

  return NextResponse.json(updated);
}
