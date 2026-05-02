/**
 * CatalogRepository contract.
 *
 *   list()                          -> CatalogItem[]
 *   get(id)                         -> CatalogItem | null
 *   create({ name, description, price, category, available }) -> CatalogItem
 *
 * CatalogItem rows match the Drizzle schema:
 *   { id, name, description, price, category, available }
 */

const { assertHasMethods } = require('../shared/repository');

const REQUIRED_METHODS = ['list', 'get', 'create'];

function assertCatalogRepository(repo) {
  assertHasMethods(repo, REQUIRED_METHODS, 'CatalogRepository');
}

module.exports = { assertCatalogRepository, REQUIRED_METHODS };
