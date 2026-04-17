/**
 * GET /api/state — return all state slices for the authenticated user.
 *
 * Response shape: { "key1": "jsonString1", "key2": "jsonString2" }
 * (values are JSON strings — the client handles decode).
 */

import { NextResponse } from 'next/server';
import { getDb } from '../../../lib/db';
import { authenticateRequest } from '../../../lib/auth';

export async function GET(request) {
  let user;
  try {
    user = await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Authentication required' }, { status: 401 });
  }

  const db = getDb();
  const rows = db.prepare('SELECT key, value FROM react_state WHERE user_id = ?').all(user.sub);

  const result = {};
  for (const row of rows) {
    result[row.key] = row.value;
  }

  return NextResponse.json(result);
}
