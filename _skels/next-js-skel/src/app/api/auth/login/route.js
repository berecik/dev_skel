import { NextResponse } from 'next/server';
import { eq } from 'drizzle-orm';
import { getDb } from '../../../../lib/db';
import { verifyPassword, createToken } from '../../../../lib/auth';
import { users } from '../../../../lib/schema';

/**
 * POST /api/auth/login
 * Body: { username, password }
 * Returns 200 { access: "<jwt>" }
 */
export async function POST(request) {
  try {
    const body = await request.json();
    const { username, password } = body;

    if (!username || !password) {
      return NextResponse.json(
        { error: 'username and password are required' },
        { status: 400 }
      );
    }

    const db = getDb();
    // Allow login by email or username -- decide which column to match on.
    const lookupColumn = username.includes('@') ? users.email : users.username;
    const user = db.select().from(users).where(eq(lookupColumn, username)).get();

    if (!user) {
      return NextResponse.json({ error: 'Invalid credentials' }, { status: 401 });
    }

    const valid = await verifyPassword(password, user.password_hash);
    if (!valid) {
      return NextResponse.json({ error: 'Invalid credentials' }, { status: 401 });
    }

    const token = await createToken({
      sub: String(user.id),
      username: user.username,
    });

    return NextResponse.json({ access: token }, { status: 200 });
  } catch (err) {
    if (err instanceof SyntaxError) {
      return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
    }
    console.error('Login error:', err);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
