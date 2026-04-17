/**
 * PUT  /api/state/:key — upsert a single state slice.
 * DELETE /api/state/:key — delete a single state slice.
 *
 * PUT body: { "value": "<json string>" }
 */

import { NextResponse } from 'next/server';
import { getDb } from '../../../../lib/db';
import { authenticateRequest } from '../../../../lib/auth';

export async function PUT(request, { params }) {
  let user;
  try {
    user = await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Authentication required' }, { status: 401 });
  }

  const { key } = await params;
  const body = await request.json();
  const value = body.value ?? '';

  const db = getDb();
  const now = new Date().toISOString().replace('T', ' ').split('.')[0];

  db.prepare(`
    INSERT INTO react_state (user_id, key, value, updated_at)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
  `).run(user.sub, key, value, now);

  return NextResponse.json({ key, value, updated_at: now });
}

export async function DELETE(request, { params }) {
  let user;
  try {
    user = await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Authentication required' }, { status: 401 });
  }

  const { key } = await params;

  const db = getDb();
  db.prepare('DELETE FROM react_state WHERE user_id = ? AND key = ?').run(user.sub, key);

  return NextResponse.json({ deleted: key });
}
