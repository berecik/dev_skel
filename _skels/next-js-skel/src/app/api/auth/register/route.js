import { NextResponse } from 'next/server';
import { getDb } from '../../../../lib/db';
import { hashPassword } from '../../../../lib/auth';
import { users } from '../../../../lib/schema';

/**
 * POST /api/auth/register
 * Body: { username, email, password, password_confirm }
 * Returns 201 { user: { id, username, email } }
 */
export async function POST(request) {
  try {
    const body = await request.json();
    const { username, email, password, password_confirm } = body;

    // Validate required fields
    if (!username || !password) {
      return NextResponse.json(
        { error: 'username and password are required' },
        { status: 400 }
      );
    }

    // Validate password confirmation
    if (password_confirm !== undefined && password !== password_confirm) {
      return NextResponse.json(
        { error: 'password and password_confirm do not match' },
        { status: 400 }
      );
    }

    const db = getDb();
    const passwordHash = await hashPassword(password);

    try {
      const created = db
        .insert(users)
        .values({
          username,
          email: email || null,
          password_hash: passwordHash,
        })
        .returning()
        .get();

      return NextResponse.json(
        {
          user: {
            id: created.id,
            username: created.username,
            email: created.email,
          },
        },
        { status: 201 }
      );
    } catch (err) {
      if (err.message && err.message.includes('UNIQUE constraint failed')) {
        return NextResponse.json({ error: 'Username already exists' }, { status: 409 });
      }
      throw err;
    }
  } catch (err) {
    if (err instanceof SyntaxError) {
      return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
    }
    console.error('Register error:', err);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
