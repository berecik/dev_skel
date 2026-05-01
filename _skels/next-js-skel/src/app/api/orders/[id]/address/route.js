import { NextResponse } from 'next/server';
import { eq, and } from 'drizzle-orm';
import { getDb } from '../../../../../lib/db';
import { authenticateRequest } from '../../../../../lib/auth';
import { orders, orderAddresses } from '../../../../../lib/schema';

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
    return NextResponse.json({ error: 'Order must be in draft status' }, { status: 400 });
  }

  try {
    const body = await request.json();
    const { street, city, zip_code, phone, notes } = body;

    if (!street || !city || !zip_code) {
      return NextResponse.json(
        { error: 'street, city, and zip_code are required' },
        { status: 400 },
      );
    }

    const existing = db
      .select()
      .from(orderAddresses)
      .where(eq(orderAddresses.order_id, orderId))
      .get();

    if (existing) {
      db.update(orderAddresses)
        .set({
          street,
          city,
          zip_code,
          phone: phone || '',
          notes: notes || '',
        })
        .where(eq(orderAddresses.order_id, orderId))
        .run();
    } else {
      db.insert(orderAddresses)
        .values({
          order_id: orderId,
          street,
          city,
          zip_code,
          phone: phone || '',
          notes: notes || '',
        })
        .run();
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
