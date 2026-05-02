/**
 * ItemRepository contract.
 *
 * Methods every implementation must provide:
 *
 *   list()                     -> Item[]
 *   get(id)                    -> Item | null
 *   create({ name, description, is_completed, category_id, owner_id }) -> Item
 *   update(id, patch)          -> Item | null
 *   delete(id)                 -> boolean (true on success)
 *   complete(id)               -> Item | null
 *   clearCategory(categoryId)  -> void   (sets category_id = NULL on every
 *                                         row referencing this category;
 *                                         called by the categories
 *                                         service before deleting the
 *                                         category to preserve SET NULL
 *                                         semantics across drivers)
 *
 * Item rows match the Drizzle schema:
 *   { id, name, description, is_completed, category_id,
 *     owner_id, created_at, updated_at }
 */

const { assertHasMethods } = require('../shared/repository');

const REQUIRED_METHODS = [
  'list',
  'get',
  'create',
  'update',
  'delete',
  'complete',
  'clearCategory',
];

function assertItemRepository(repo) {
  assertHasMethods(repo, REQUIRED_METHODS, 'ItemRepository');
}

module.exports = { assertItemRepository, REQUIRED_METHODS };
