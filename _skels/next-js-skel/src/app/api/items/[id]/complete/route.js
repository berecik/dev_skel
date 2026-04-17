import { NextResponse } from 'next/server';
import { getDb } from '../../../../../lib/db';
import { authenticateRequest } from '../../../../../lib/auth';

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
  const db = getDb();

  const existing = db.prepare('SELECT * FROM items WHERE id = ?').get(Number(id));
  if (!existing) {
    return NextResponse.json({ error: 'Item not found' }, { status: 404 });
  }

  db.prepare('UPDATE items SET is_completed = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?').run(
    Number(id)
  );

  const updated = db.prepare('SELECT * FROM items WHERE id = ?').get(Number(id));
  return NextResponse.json(formatItem(updated));
}
