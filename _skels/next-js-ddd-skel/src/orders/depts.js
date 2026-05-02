/**
 * Composition root for the orders resource.
 */

const { DrizzleOrderRepository } = require('./adapters/sql');
const { OrdersService } = require('./service');

function buildOrderRepository(db) {
  return new DrizzleOrderRepository(db);
}

function buildOrdersService(db) {
  return new OrdersService(buildOrderRepository(db));
}

module.exports = { buildOrderRepository, buildOrdersService };
