/**
 * CategoryRepository contract.
 *
 *   list()                 -> Category[]
 *   get(id)                -> Category | null
 *   create({ name, description }) -> Category
 *   update(id, patch)      -> Category | null
 *   delete(id)             -> boolean (true on success)
 *
 * Category rows match the Drizzle schema:
 *   { id, name, description, created_at, updated_at }
 */

const { assertHasMethods } = require('../shared/repository');

const REQUIRED_METHODS = ['list', 'get', 'create', 'update', 'delete'];

function assertCategoryRepository(repo) {
  assertHasMethods(repo, REQUIRED_METHODS, 'CategoryRepository');
}

module.exports = { assertCategoryRepository, REQUIRED_METHODS };
