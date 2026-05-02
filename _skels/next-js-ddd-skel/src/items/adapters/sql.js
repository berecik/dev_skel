/**
 * Drizzle-backed implementation of ItemRepository.
 */

const { eq } = require('drizzle-orm');
const { items } = require('../../lib/schema');
const { wrapDb } = require('../../shared/errors');

class DrizzleItemRepository {
  constructor(db) {
    if (!db) throw new Error('DrizzleItemRepository requires a Drizzle db handle');
    this.db = db;
  }

  list() {
    return this.db.select().from(items).all();
  }

  get(id) {
    return this.db.select().from(items).where(eq(items.id, Number(id))).get() || null;
  }

  create({ name, description, is_completed, category_id, owner_id }) {
    try {
      return this.db
        .insert(items)
        .values({
          name,
          description: description ?? null,
          is_completed: Boolean(is_completed),
          category_id: category_id ?? null,
          owner_id: owner_id ?? null,
        })
        .returning()
        .get();
    } catch (err) {
      throw wrapDb(err);
    }
  }

  update(id, patch) {
    const itemId = Number(id);
    const existing = this.get(itemId);
    if (!existing) return null;

    const next = {
      name: patch.name !== undefined ? patch.name : existing.name,
      description: patch.description !== undefined ? patch.description : existing.description,
      is_completed:
        patch.is_completed !== undefined ? Boolean(patch.is_completed) : existing.is_completed,
      category_id:
        patch.category_id !== undefined ? patch.category_id : existing.category_id,
      updated_at: new Date(),
    };

    try {
      return this.db.update(items).set(next).where(eq(items.id, itemId)).returning().get();
    } catch (err) {
      throw wrapDb(err);
    }
  }

  delete(id) {
    const itemId = Number(id);
    const existing = this.get(itemId);
    if (!existing) return false;
    this.db.delete(items).where(eq(items.id, itemId)).run();
    return true;
  }

  complete(id) {
    const itemId = Number(id);
    const existing = this.get(itemId);
    if (!existing) return null;
    return this.db
      .update(items)
      .set({ is_completed: true, updated_at: new Date() })
      .where(eq(items.id, itemId))
      .returning()
      .get();
  }

  clearCategory(categoryId) {
    this.db
      .update(items)
      .set({ category_id: null, updated_at: new Date() })
      .where(eq(items.category_id, Number(categoryId)))
      .run();
  }
}

module.exports = { DrizzleItemRepository };
