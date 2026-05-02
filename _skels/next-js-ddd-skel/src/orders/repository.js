/**
 * OrderRepository contract — orders are an aggregate (header +
 * lines + address). The repository keeps the three together so
 * services see one transactional surface.
 *
 *   listForUser(userId)                 -> Order[]
 *   getRaw(orderId)                     -> Order | null  (header only, no user scope —
 *                                                         used by approve/reject)
 *   getForUser(userId, orderId)         -> Order | null  (header only)
 *   getDetailForUser(userId, orderId)   -> { ...Order, lines, address } | null
 *   createDraft(userId)                 -> Order
 *   addLine(orderId, { catalog_item_id, quantity, unit_price }) -> OrderLine
 *   getLine(orderId, lineId)            -> OrderLine | null
 *   removeLine(orderId, lineId)         -> boolean
 *   setAddress(orderId, addr)           -> void   (insert-or-update)
 *   getAddress(orderId)                 -> Address | null
 *   listLines(orderId)                  -> OrderLine[]
 *   updateStatus(orderId, status, patch?) -> Order | null
 *   getCatalogItem(catalogItemId)       -> CatalogItem | null
 */

const { assertHasMethods } = require('../shared/repository');

const REQUIRED_METHODS = [
  'listForUser',
  'getRaw',
  'getForUser',
  'getDetailForUser',
  'createDraft',
  'addLine',
  'getLine',
  'removeLine',
  'setAddress',
  'getAddress',
  'listLines',
  'updateStatus',
  'getCatalogItem',
];

function assertOrderRepository(repo) {
  assertHasMethods(repo, REQUIRED_METHODS, 'OrderRepository');
}

module.exports = { assertOrderRepository, REQUIRED_METHODS };
