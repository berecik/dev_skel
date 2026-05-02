/**
 * StateService — per-user JSON-string KV store.
 *
 * Mirrors the pre-DDD flat routes byte-for-byte: list returns a
 * `{ key: value }` map, upsert returns `{ key, value, updated_at }`,
 * delete returns `{ deleted: key }` (the route layer wraps that).
 */

const { assertStateRepository } = require('./repository');

class StateService {
  constructor(repo) {
    assertStateRepository(repo);
    this.repo = repo;
  }

  list(userId) {
    return this.repo.listForUser(userId);
  }

  upsert(userId, key, value) {
    return this.repo.upsertForUser(userId, key, value ?? '');
  }

  delete(userId, key) {
    this.repo.deleteForUser(userId, key);
    return { deleted: key };
  }
}

module.exports = { StateService };
