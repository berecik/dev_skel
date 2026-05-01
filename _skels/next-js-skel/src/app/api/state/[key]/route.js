/**
 * PUT  /api/state/:key — upsert a single state slice.
 * DELETE /api/state/:key — delete a single state slice.
 *
 * PUT body: { "value": "<json string>" }
 */

import { NextResponse } from 'next/server';
import { eq, and } from 'drizzle-orm';
import { getDb } from '../../../../lib/db';
import { authenticateRequest } from '../../../../lib/auth';
import { reactState } from '../../../../lib/schema';

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
  const userId = Number(user.sub);
  const now = new Date();

  const db = getDb();
  db.insert(reactState)
    .values({ user_id: userId, key, value, updated_at: now })
    .onConflictDoUpdate({
      target: [reactState.user_id, reactState.key],
      set: { value, updated_at: now },
    })
    .run();

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
  const userId = Number(user.sub);

  const db = getDb();
  db.delete(reactState)
    .where(and(eq(reactState.user_id, userId), eq(reactState.key, key)))
    .run();

  return NextResponse.json({ deleted: key });
}
