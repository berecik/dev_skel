/**
 * Drizzle-backed implementation of CategoryRepository.
 */

const { eq, asc } = require('drizzle-orm');
const { categories } = require('../../lib/schema');
const { wrapDb } = require('../../shared/errors');

class DrizzleCategoryRepository {
  constructor(db) {
    if (!db) throw new Error('DrizzleCategoryRepository requires a Drizzle db handle');
    this.db = db;
  }

  list() {
    return this.db.select().from(categories).orderBy(asc(categories.name)).all();
  }

  get(id) {
    return (
      this.db.select().from(categories).where(eq(categories.id, Number(id))).get() || null
    );
  }

  create({ name, description }) {
    try {
      return this.db
        .insert(categories)
        .values({ name, description: description ?? null })
        .returning()
        .get();
    } catch (err) {
      throw wrapDb(err);
    }
  }

  update(id, patch) {
    const categoryId = Number(id);
    const existing = this.get(categoryId);
    if (!existing) return null;

    const next = {
      name: patch.name !== undefined ? patch.name : existing.name,
      description:
        patch.description !== undefined ? patch.description : existing.description,
      updated_at: new Date(),
    };

    try {
      return this.db
        .update(categories)
        .set(next)
        .where(eq(categories.id, categoryId))
        .returning()
        .get();
    } catch (err) {
      throw wrapDb(err);
    }
  }

  delete(id) {
    const categoryId = Number(id);
    const existing = this.get(categoryId);
    if (!existing) return false;
    this.db.delete(categories).where(eq(categories.id, categoryId)).run();
    return true;
  }
}

module.exports = { DrizzleCategoryRepository };
