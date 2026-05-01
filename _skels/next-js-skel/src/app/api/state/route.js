/**
 * GET /api/state — return all state slices for the authenticated user.
 *
 * Response shape: { "key1": "jsonString1", "key2": "jsonString2" }
 * (values are JSON strings — the client handles decode).
 */

import { NextResponse } from 'next/server';
import { eq } from 'drizzle-orm';
import { getDb } from '../../../lib/db';
import { authenticateRequest } from '../../../lib/auth';
import { reactState } from '../../../lib/schema';

export async function GET(request) {
  let user;
  try {
    user = await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Authentication required' }, { status: 401 });
  }

  const db = getDb();
  const rows = db
    .select({ key: reactState.key, value: reactState.value })
    .from(reactState)
    .where(eq(reactState.user_id, Number(user.sub)))
    .all();

  const result = {};
  for (const row of rows) {
    result[row.key] = row.value;
  }

  return NextResponse.json(result);
}
