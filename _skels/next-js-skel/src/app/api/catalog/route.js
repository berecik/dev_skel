import { NextResponse } from 'next/server';
import { getDb } from '../../../lib/db';
import { authenticateRequest } from '../../../lib/auth';

/**
 * GET /api/catalog
 * Returns 200 with array of catalog items.
 */
export async function GET() {
  const db = getDb();
  const rows = db.prepare('SELECT * FROM catalog_items ORDER BY name').all();
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
    const stmt = db.prepare(
      'INSERT INTO catalog_items (name, description, price, category, available) VALUES (?, ?, ?, ?, ?)'
    );
    const result = stmt.run(
      name,
      description || '',
      price || 0.0,
      category || '',
      available !== false ? 1 : 0,
    );

    const created = db.prepare('SELECT * FROM catalog_items WHERE id = ?').get(result.lastInsertRowid);
    return NextResponse.json(created, { status: 201 });
  } catch (err) {
    if (err instanceof SyntaxError) {
      return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
    }
    console.error('Create catalog item error:', err);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
