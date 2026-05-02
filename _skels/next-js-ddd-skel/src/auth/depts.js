/**
 * Composition root for the auth resource.
 */

const { DrizzleUserRepository } = require('../users/adapters/sql');
const { AuthService } = require('./service');

function buildUserRepository(db) {
  return new DrizzleUserRepository(db);
}

function buildAuthService(db) {
  return new AuthService(buildUserRepository(db));
}

module.exports = { buildUserRepository, buildAuthService };
