/**
 * Composition root for the state resource.
 */

const { DrizzleStateRepository } = require('./adapters/sql');
const { StateService } = require('./service');

function buildStateRepository(db) {
  return new DrizzleStateRepository(db);
}

function buildStateService(db) {
  return new StateService(buildStateRepository(db));
}

module.exports = { buildStateRepository, buildStateService };
