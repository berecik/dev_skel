import { NextResponse } from 'next/server';
import { eq } from 'drizzle-orm';
import { getDb } from '../../../../lib/db';
import { authenticateRequest } from '../../../../lib/auth';
import { catalogItems } from '../../../../lib/schema';

/**
 * GET /api/catalog/[id]
 * Returns 200 with the catalog item, or 404. Requires Bearer auth.
 */
export async function GET(request, { params }) {
  try {
    await authenticateRequest(request);
  } catch {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { id } = await params;
  const db = getDb();
  const row = db.select().from(catalogItems).where(eq(catalogItems.id, Number(id))).get();

  if (!row) {
    return NextResponse.json({ error: 'Catalog item not found' }, { status: 404 });
  }

  return NextResponse.json(row);
}
