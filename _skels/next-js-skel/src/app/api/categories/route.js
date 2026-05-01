import { NextResponse } from 'next/server';
import { asc } from 'drizzle-orm';
import { getDb } from '../../../lib/db';
import { authenticateRequest } from '../../../lib/auth';
import { categories } from '../../../lib/schema';

/**
 * GET /api/categories
 * Returns 200 with array of categories. Requires Bearer auth.
 */
export async function GET(request) {
  try {
    await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const db = getDb();
  const rows = db.select().from(categories).orderBy(asc(categories.name)).all();
  return NextResponse.json(rows);
}

/**
 * POST /api/categories
 * Body: { name, description? }
 * Returns 201 with the created category. Requires Bearer auth.
 */
export async function POST(request) {
  try {
    await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const body = await request.json();
    const { name, description } = body;

    if (!name) {
      return NextResponse.json({ error: 'name is required' }, { status: 400 });
    }

    const db = getDb();
    const created = db
      .insert(categories)
      .values({ name, description: description || null })
      .returning()
      .get();

    return NextResponse.json(created, { status: 201 });
  } catch (err) {
    if (err instanceof SyntaxError) {
      return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
    }
    if (err.message && err.message.includes('UNIQUE constraint failed')) {
      return NextResponse.json({ error: 'Category name already exists' }, { status: 409 });
    }
    console.error('Create category error:', err);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
