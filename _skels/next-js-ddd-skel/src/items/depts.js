/**
 * Composition root for the items resource.
 *
 * The route files import `buildItemsService(db)` from here so they
 * never reach for the adapter or schema themselves. Tests can call
 * the same function with an in-memory Drizzle handle from
 * `lib/db.js::createTestDb()`.
 */

const { DrizzleItemRepository } = require('./adapters/sql');
const { ItemsService } = require('./service');

function buildItemsRepository(db) {
  return new DrizzleItemRepository(db);
}

function buildItemsService(db) {
  return new ItemsService(buildItemsRepository(db));
}

module.exports = { buildItemsRepository, buildItemsService };
