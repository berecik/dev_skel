/**
 * Composition root for the catalog resource.
 */

const { DrizzleCatalogRepository } = require('./adapters/sql');
const { CatalogService } = require('./service');

function buildCatalogRepository(db) {
  return new DrizzleCatalogRepository(db);
}

function buildCatalogService(db) {
  return new CatalogService(buildCatalogRepository(db));
}

module.exports = { buildCatalogRepository, buildCatalogService };
