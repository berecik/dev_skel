import { NextResponse } from 'next/server';
import { getDb } from '../../../lib/db';
import { authenticateRequest } from '../../../lib/auth';
import { items } from '../../../lib/schema';

/**
 * GET /api/items
 * Returns 200 with array of items. Requires Bearer auth.
 */
export async function GET(request) {
  try {
    await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const db = getDb();
  const rows = db.select().from(items).all();
  return NextResponse.json(rows);
}

/**
 * POST /api/items
 * Body: { name, description?, is_completed?, category_id? }
 * Returns 201 with the created item. Requires Bearer auth.
 */
export async function POST(request) {
  let user;
  try {
    user = await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const body = await request.json();
    const { name, description, is_completed, category_id } = body;

    if (!name) {
      return NextResponse.json({ error: 'name is required' }, { status: 400 });
    }

    const db = getDb();
    const ownerId = user.sub ? Number(user.sub) : null;

    const created = db
      .insert(items)
      .values({
        name,
        description: description || null,
        is_completed: Boolean(is_completed),
        category_id: category_id ?? null,
        owner_id: ownerId,
      })
      .returning()
      .get();

    return NextResponse.json(created, { status: 201 });
  } catch (err) {
    if (err instanceof SyntaxError) {
      return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
    }
    console.error('Create item error:', err);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
