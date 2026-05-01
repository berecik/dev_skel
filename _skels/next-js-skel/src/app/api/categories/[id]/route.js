import { NextResponse } from 'next/server';
import { eq } from 'drizzle-orm';
import { getDb } from '../../../../lib/db';
import { authenticateRequest } from '../../../../lib/auth';
import { categories } from '../../../../lib/schema';

/**
 * GET /api/categories/[id]
 * Returns 200 with the category, or 404. Requires Bearer auth.
 */
export async function GET(request, { params }) {
  try {
    await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { id } = await params;
  const db = getDb();
  const row = db.select().from(categories).where(eq(categories.id, Number(id))).get();

  if (!row) {
    return NextResponse.json({ error: 'Category not found' }, { status: 404 });
  }

  return NextResponse.json(row);
}

/**
 * PUT /api/categories/[id]
 * Body: { name?, description? }
 * Returns 200 with the updated category, or 404. Requires Bearer auth.
 */
export async function PUT(request, { params }) {
  try {
    await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { id } = await params;
  const categoryId = Number(id);
  const db = getDb();

  const existing = db.select().from(categories).where(eq(categories.id, categoryId)).get();
  if (!existing) {
    return NextResponse.json({ error: 'Category not found' }, { status: 404 });
  }

  try {
    const body = await request.json();
    const { name, description } = body;

    const updated = db
      .update(categories)
      .set({
        name: name !== undefined ? name : existing.name,
        description: description !== undefined ? description : existing.description,
        updated_at: new Date(),
      })
      .where(eq(categories.id, categoryId))
      .returning()
      .get();

    return NextResponse.json(updated);
  } catch (err) {
    if (err instanceof SyntaxError) {
      return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
    }
    if (err.message && err.message.includes('UNIQUE constraint failed')) {
      return NextResponse.json({ error: 'Category name already exists' }, { status: 409 });
    }
    console.error('Update category error:', err);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

/**
 * DELETE /api/categories/[id]
 * Deletes the category. Returns 204 on success, or 404. Requires Bearer auth.
 */
export async function DELETE(request, { params }) {
  try {
    await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { id } = await params;
  const categoryId = Number(id);
  const db = getDb();

  const existing = db.select().from(categories).where(eq(categories.id, categoryId)).get();
  if (!existing) {
    return NextResponse.json({ error: 'Category not found' }, { status: 404 });
  }

  db.delete(categories).where(eq(categories.id, categoryId)).run();
  return new NextResponse(null, { status: 204 });
}
