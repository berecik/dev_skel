/**
 * Seed module — creates default user accounts from environment variables.
 *
 * Reads USER_* and SUPERUSER_* env vars (via config) and inserts the
 * corresponding rows into the `users` table if they do not already exist.
 * Passwords are hashed with bcrypt before storage.
 *
 * Called automatically by `getDb()` after schema initialisation so that
 * every first run of a fresh skeleton already has usable accounts.
 */

const bcrypt = require('bcryptjs');

const SALT_ROUNDS = 12;

/**
 * Synchronously hash a password with bcrypt.
 * We intentionally use the sync variant here because better-sqlite3 is
 * synchronous and the seed runs once at startup — there is no request
 * to block.
 */
function hashPasswordSync(password) {
  return bcrypt.hashSync(password, SALT_ROUNDS);
}

/**
 * Insert a user row if the username does not already exist.
 */
function upsertUser(db, { username, email, password }) {
  if (!username || !password) return;

  const existing = db.prepare('SELECT id FROM users WHERE username = ?').get(username);
  if (existing) return;

  const hash = hashPasswordSync(password);
  db.prepare(
    'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)'
  ).run(username, email || null, hash);
}

/**
 * Seed default accounts defined by environment variables.
 *
 * Reads directly from process.env rather than config to work reliably
 * in both standalone Node and Next.js server modes.
 */
function seedDefaultAccounts(db) {
  const accounts = [
    {
      username: process.env.USER_LOGIN || 'user',
      email: process.env.USER_EMAIL || 'user@example.com',
      password: process.env.USER_PASSWORD || 'secret',
    },
    {
      username: process.env.SUPERUSER_LOGIN || 'admin',
      email: process.env.SUPERUSER_EMAIL || 'admin@example.com',
      password: process.env.SUPERUSER_PASSWORD || 'secret',
    },
  ];
  for (const account of accounts) {
    upsertUser(db, account);
  }
}

module.exports = { seedDefaultAccounts };
