/**
 * CategoriesService.
 *
 * `delete(id)` explicitly clears the category from every referencing
 * item before removing the category row. The Drizzle schema declares
 * `ON DELETE SET NULL` on the FK, but doing it in service code keeps
 * the behaviour driver-portable (the FK action is enforced only
 * when SQLite has `foreign_keys = ON`, which Postgres does not need
 * but other drivers/configurations might miss).
 */

const { DomainError } = require('../shared/errors');
const { assertCategoryRepository } = require('./repository');

class CategoriesService {
  constructor(categoryRepo, itemRepo) {
    assertCategoryRepository(categoryRepo);
    if (!itemRepo || typeof itemRepo.clearCategory !== 'function') {
      throw new Error('CategoriesService requires an ItemRepository with clearCategory()');
    }
    this.repo = categoryRepo;
    this.items = itemRepo;
  }

  list() {
    return this.repo.list();
  }

  get(id) {
    const row = this.repo.get(id);
    if (!row) throw DomainError.notFound('Category not found');
    return row;
  }

  create({ name, description }) {
    if (!name || typeof name !== 'string') {
      throw DomainError.validation('name is required');
    }
    return this.repo.create({ name, description: description ?? null });
  }

  update(id, patch) {
    const updated = this.repo.update(id, patch || {});
    if (!updated) throw DomainError.notFound('Category not found');
    return updated;
  }

  delete(id) {
    const existing = this.repo.get(id);
    if (!existing) throw DomainError.notFound('Category not found');
    this.items.clearCategory(id);
    this.repo.delete(id);
  }
}

module.exports = { CategoriesService };
