import { NextResponse } from 'next/server';
import { eq } from 'drizzle-orm';
import { getDb } from '../../../../lib/db';
import { authenticateRequest } from '../../../../lib/auth';
import { items } from '../../../../lib/schema';

/**
 * GET /api/items/[id]
 * Returns 200 with the item, or 404. Requires Bearer auth.
 */
export async function GET(request, { params }) {
  try {
    await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { id } = await params;
  const db = getDb();
  const row = db.select().from(items).where(eq(items.id, Number(id))).get();

  if (!row) {
    return NextResponse.json({ error: 'Item not found' }, { status: 404 });
  }

  return NextResponse.json(row);
}
