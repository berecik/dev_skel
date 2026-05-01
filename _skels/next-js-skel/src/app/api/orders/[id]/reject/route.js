import { NextResponse } from 'next/server';
import { eq } from 'drizzle-orm';
import { getDb } from '../../../../../lib/db';
import { authenticateRequest } from '../../../../../lib/auth';
import { orders } from '../../../../../lib/schema';

/**
 * POST /api/orders/[id]/reject
 * Body: { feedback? }
 * Transitions a pending order to rejected status.
 * Returns 200 with the updated order. Requires Bearer auth.
 */
export async function POST(request, { params }) {
  try {
    await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { id } = await params;
  const orderId = Number(id);
  const db = getDb();

  const order = db.select().from(orders).where(eq(orders.id, orderId)).get();
  if (!order) {
    return NextResponse.json({ error: 'Order not found' }, { status: 404 });
  }

  if (order.status !== 'pending') {
    return NextResponse.json({ error: 'Only pending orders can be rejected' }, { status: 400 });
  }

  try {
    const body = await request.json();
    const { feedback } = body;

    const updated = db
      .update(orders)
      .set({
        status: 'rejected',
        feedback: feedback || null,
        updated_at: new Date(),
      })
      .where(eq(orders.id, orderId))
      .returning()
      .get();

    return NextResponse.json(updated);
  } catch (err) {
    if (err instanceof SyntaxError) {
      return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
    }
    console.error('Reject order error:', err);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
