/**
 * UserRepository contract.
 *
 * The `users` resource has no public routes (auth is the only caller),
 * so this module only declares the repository surface and a runtime
 * guard. The Drizzle adapter lives at `./adapters/sql.js`.
 *
 * Methods every implementation must provide:
 *
 *   findById(id)              -> User | null
 *   findByUsername(username)  -> User | null
 *   findByEmail(email)        -> User | null
 *   findByLogin(login)        -> User | null  (email if it contains '@', else username)
 *   create({ username, email, password_hash }) -> User
 *
 * `User` is the plain object returned by the adapter — it matches the
 * Drizzle schema row shape: { id, username, email, password_hash,
 * created_at }.
 */

const { assertHasMethods } = require('../shared/repository');

const REQUIRED_METHODS = ['findById', 'findByUsername', 'findByEmail', 'findByLogin', 'create'];

function assertUserRepository(repo) {
  assertHasMethods(repo, REQUIRED_METHODS, 'UserRepository');
}

module.exports = { assertUserRepository, REQUIRED_METHODS };
