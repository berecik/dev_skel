import { NextResponse } from 'next/server';
import { getDb } from '../../../../lib/db';
import { authenticateRequest } from '../../../../lib/auth';

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
    category_id: row.category_id ?? null,
    owner_id: row.owner_id,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

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
  const row = db.prepare('SELECT * FROM items WHERE id = ?').get(Number(id));

  if (!row) {
    return NextResponse.json({ error: 'Item not found' }, { status: 404 });
  }

  return NextResponse.json(formatItem(row));
}
