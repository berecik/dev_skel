import { NextResponse } from 'next/server';
import { eq } from 'drizzle-orm';
import { getDb } from '../../../../../lib/db';
import { authenticateRequest } from '../../../../../lib/auth';
import { items } from '../../../../../lib/schema';

/**
 * POST /api/items/[id]/complete
 * Marks the item as completed. Returns 200 with the updated item, or 404.
 * Requires Bearer auth.
 */
export async function POST(request, { params }) {
  try {
    await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { id } = await params;
  const itemId = Number(id);
  const db = getDb();

  const existing = db.select().from(items).where(eq(items.id, itemId)).get();
  if (!existing) {
    return NextResponse.json({ error: 'Item not found' }, { status: 404 });
  }

  const updated = db
    .update(items)
    .set({ is_completed: true, updated_at: new Date() })
    .where(eq(items.id, itemId))
    .returning()
    .get();

  return NextResponse.json(updated);
}
