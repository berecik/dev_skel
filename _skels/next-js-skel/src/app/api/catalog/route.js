import { NextResponse } from 'next/server';
import { asc } from 'drizzle-orm';
import { getDb } from '../../../lib/db';
import { authenticateRequest } from '../../../lib/auth';
import { catalogItems } from '../../../lib/schema';

/**
 * GET /api/catalog
 * Returns 200 with array of catalog items.
 */
export async function GET() {
  const db = getDb();
  const rows = db.select().from(catalogItems).orderBy(asc(catalogItems.name)).all();
  return NextResponse.json(rows);
}

/**
 * POST /api/catalog
 * Body: { name, price, category?, description?, available? }
 * Returns 201 with the created catalog item. Requires Bearer auth.
 */
export async function POST(request) {
  try {
    await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const body = await request.json();
    const { name, price, category, description, available } = body;

    if (!name) {
      return NextResponse.json({ error: 'name is required' }, { status: 400 });
    }

    const db = getDb();
    const created = db
      .insert(catalogItems)
      .values({
        name,
        description: description || '',
        price: price || 0.0,
        category: category || '',
        available: available !== false,
      })
      .returning()
      .get();

    return NextResponse.json(created, { status: 201 });
  } catch (err) {
    if (err instanceof SyntaxError) {
      return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
    }
    console.error('Create catalog item error:', err);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
