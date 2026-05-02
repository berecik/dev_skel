/**
 * ItemsService — pure domain logic, framework-agnostic.
 *
 * Depends only on an `ItemRepository` (duck-typed; verified at
 * construction time via `assertItemRepository`). Throws DomainError
 * on any expected failure mode so the route layer can map it to the
 * right HTTP status without parsing strings.
 */

const { DomainError } = require('../shared/errors');
const { assertItemRepository } = require('./repository');

class ItemsService {
  constructor(repo) {
    assertItemRepository(repo);
    this.repo = repo;
  }

  list() {
    return this.repo.list();
  }

  get(id) {
    const row = this.repo.get(id);
    if (!row) throw DomainError.notFound('Item not found');
    return row;
  }

  create({ name, description, is_completed, category_id, owner_id }) {
    if (!name || typeof name !== 'string') {
      throw DomainError.validation('name is required');
    }
    return this.repo.create({
      name,
      description: description ?? null,
      is_completed: Boolean(is_completed),
      category_id: category_id ?? null,
      owner_id: owner_id ?? null,
    });
  }

  update(id, patch) {
    const updated = this.repo.update(id, patch || {});
    if (!updated) throw DomainError.notFound('Item not found');
    return updated;
  }

  delete(id) {
    const removed = this.repo.delete(id);
    if (!removed) throw DomainError.notFound('Item not found');
  }

  complete(id) {
    const updated = this.repo.complete(id);
    if (!updated) throw DomainError.notFound('Item not found');
    return updated;
  }
}

module.exports = { ItemsService };
