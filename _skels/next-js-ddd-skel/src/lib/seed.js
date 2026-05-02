/**
 * Seed module — creates default user accounts from environment variables.
 *
 * In the DDD layout, seed takes a `UserRepository` rather than a raw
 * Drizzle handle. The repository abstraction lets the seed step share
 * the same query-building & error-wrapping path that the auth flow
 * uses, and makes it trivial to replace storage in tests.
 *
 * For backwards compatibility with the static `lib/db.js` initialiser,
 * `seedDefaultAccounts` still accepts a raw db handle and lazy-builds
 * a `DrizzleUserRepository` internally.
 *
 * Called automatically by `getDb()` after schema initialisation so that
 * every first run of a fresh skeleton already has usable accounts.
 */

const bcrypt = require('bcryptjs');

const SALT_ROUNDS = 12;

/**
 * Synchronously hash a password with bcrypt.
 *
 * better-sqlite3 is synchronous and seeding runs once at startup, so
 * blocking here is a non-issue.
 */
function hashPasswordSync(password) {
  return bcrypt.hashSync(password, SALT_ROUNDS);
}

/**
 * Insert a user row through the supplied repository if the username
 * does not already exist.
 */
function upsertUser(userRepository, { username, email, password }) {
  if (!username || !password) return;
  if (userRepository.findByUsername(username)) return;
  const password_hash = hashPasswordSync(password);
  userRepository.create({ username, email: email || null, password_hash });
}

/**
 * Seed default accounts defined by environment variables.
 *
 * Accepts EITHER a `UserRepository` (preferred) OR a raw Drizzle db
 * handle (legacy — wrapped on the fly).
 */
function seedDefaultAccounts(userRepositoryOrDb) {
  const userRepository = looksLikeRepository(userRepositoryOrDb)
    ? userRepositoryOrDb
    : buildRepoFromDb(userRepositoryOrDb);

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
    upsertUser(userRepository, account);
  }
}

function looksLikeRepository(value) {
  return (
    value &&
    typeof value.findByUsername === 'function' &&
    typeof value.create === 'function'
  );
}

function buildRepoFromDb(db) {
  // Lazy require to avoid a require-cycle with `users/adapters/sql.js`
  // (which itself imports the schema).
  const { DrizzleUserRepository } = require('../users/adapters/sql');
  return new DrizzleUserRepository(db);
}

module.exports = { seedDefaultAccounts };
