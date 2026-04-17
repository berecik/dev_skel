import { NextResponse } from 'next/server';
import { getDb } from '../../../lib/db';
import { authenticateRequest } from '../../../lib/auth';

/**
 * Convert an item row from SQLite (is_completed as 0/1)
 * to an API response object (is_completed as boolean).
 */
function formatItem(row) {
  return {
    id: row.id,
    name: row.name,
    description: row.description,
    is_completed: row.is_completed === 1,
    owner_id: row.owner_id,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

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
  const rows = db.prepare('SELECT * FROM items').all();
  return NextResponse.json(rows.map(formatItem));
}

/**
 * POST /api/items
 * Body: { name, description?, is_completed? }
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
    const { name, description, is_completed } = body;

    if (!name) {
      return NextResponse.json({ error: 'name is required' }, { status: 400 });
    }

    const db = getDb();
    const completed = is_completed ? 1 : 0;
    const ownerId = user.sub ? Number(user.sub) : null;

    const stmt = db.prepare(
      'INSERT INTO items (name, description, is_completed, owner_id) VALUES (?, ?, ?, ?)'
    );
    const result = stmt.run(name, description || null, completed, ownerId);

    const created = db.prepare('SELECT * FROM items WHERE id = ?').get(result.lastInsertRowid);

    return NextResponse.json(formatItem(created), { status: 201 });
  } catch (err) {
    if (err instanceof SyntaxError) {
      return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
    }
    console.error('Create item error:', err);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
