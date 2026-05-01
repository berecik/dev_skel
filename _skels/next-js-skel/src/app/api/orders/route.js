import { NextResponse } from 'next/server';
import { eq, desc } from 'drizzle-orm';
import { getDb } from '../../../lib/db';
import { authenticateRequest } from '../../../lib/auth';
import { orders } from '../../../lib/schema';

/**
 * GET /api/orders
 * Returns 200 with array of orders belonging to the authenticated user.
 * Requires Bearer auth.
 */
export async function GET(request) {
  let user;
  try {
    user = await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const userId = user.sub ? Number(user.sub) : null;
  const db = getDb();
  const rows = db
    .select()
    .from(orders)
    .where(eq(orders.user_id, userId))
    .orderBy(desc(orders.created_at))
    .all();
  return NextResponse.json(rows);
}

/**
 * POST /api/orders
 * Creates a new draft order for the authenticated user.
 * Returns 201 with the created order. Requires Bearer auth.
 */
export async function POST(request) {
  let user;
  try {
    user = await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const userId = user.sub ? Number(user.sub) : null;
  const db = getDb();

  const created = db
    .insert(orders)
    .values({ user_id: userId, status: 'draft' })
    .returning()
    .get();

  return NextResponse.json(created, { status: 201 });
}
