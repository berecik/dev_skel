/**
 * Drizzle-backed implementation of UserRepository.
 *
 * Pure Drizzle queries — this is the only place outside `lib/schema.js`
 * that is allowed to import the `users` table descriptor.
 */

const { eq } = require('drizzle-orm');
const { users } = require('../../lib/schema');
const { wrapDb } = require('../../shared/errors');

class DrizzleUserRepository {
  constructor(db) {
    if (!db) throw new Error('DrizzleUserRepository requires a Drizzle db handle');
    this.db = db;
  }

  findById(id) {
    return this.db.select().from(users).where(eq(users.id, Number(id))).get() || null;
  }

  findByUsername(username) {
    return this.db.select().from(users).where(eq(users.username, username)).get() || null;
  }

  findByEmail(email) {
    return this.db.select().from(users).where(eq(users.email, email)).get() || null;
  }

  /**
   * Look up by username or email; auto-detected via '@' in the input.
   * Mirrors the previous flat /api/auth/login behaviour.
   */
  findByLogin(login) {
    if (typeof login !== 'string' || login.length === 0) return null;
    const column = login.includes('@') ? users.email : users.username;
    return this.db.select().from(users).where(eq(column, login)).get() || null;
  }

  /**
   * Insert a new user row. Throws DomainError.conflict on duplicate
   * username/email.
   */
  create({ username, email, password_hash }) {
    try {
      return this.db
        .insert(users)
        .values({
          username,
          email: email || null,
          password_hash,
        })
        .returning()
        .get();
    } catch (err) {
      throw wrapDb(err);
    }
  }
}

module.exports = { DrizzleUserRepository };
