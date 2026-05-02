/**
 * StateRepository contract — per-user JSON-string KV store.
 *
 *   listForUser(userId)               -> { [key]: stringValue }
 *   upsertForUser(userId, key, value) -> { key, value, updated_at }
 *   deleteForUser(userId, key)        -> void
 */

const { assertHasMethods } = require('../shared/repository');

const REQUIRED_METHODS = ['listForUser', 'upsertForUser', 'deleteForUser'];

function assertStateRepository(repo) {
  assertHasMethods(repo, REQUIRED_METHODS, 'StateRepository');
}

module.exports = { assertStateRepository, REQUIRED_METHODS };
