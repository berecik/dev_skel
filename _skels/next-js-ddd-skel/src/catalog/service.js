/**
 * CatalogService — list / get / create catalog items.
 *
 * Catalog items are read-mostly, listed publicly (no auth on GET) and
 * mutated via authenticated POST. The route layer enforces auth; the
 * service stays pure domain.
 */

const { DomainError } = require('../shared/errors');
const { assertCatalogRepository } = require('./repository');

class CatalogService {
  constructor(repo) {
    assertCatalogRepository(repo);
    this.repo = repo;
  }

  list() {
    return this.repo.list();
  }

  get(id) {
    const row = this.repo.get(id);
    if (!row) throw DomainError.notFound('Catalog item not found');
    return row;
  }

  create({ name, description, price, category, available }) {
    if (!name || typeof name !== 'string') {
      throw DomainError.validation('name is required');
    }
    return this.repo.create({ name, description, price, category, available });
  }
}

module.exports = { CatalogService };
