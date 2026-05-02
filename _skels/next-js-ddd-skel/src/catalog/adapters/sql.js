/**
 * Drizzle-backed implementation of CatalogRepository.
 */

const { eq, asc } = require('drizzle-orm');
const { catalogItems } = require('../../lib/schema');
const { wrapDb } = require('../../shared/errors');

class DrizzleCatalogRepository {
  constructor(db) {
    if (!db) throw new Error('DrizzleCatalogRepository requires a Drizzle db handle');
    this.db = db;
  }

  list() {
    return this.db.select().from(catalogItems).orderBy(asc(catalogItems.name)).all();
  }

  get(id) {
    return (
      this.db.select().from(catalogItems).where(eq(catalogItems.id, Number(id))).get() || null
    );
  }

  create({ name, description, price, category, available }) {
    try {
      return this.db
        .insert(catalogItems)
        .values({
          name,
          description: description || '',
          price: price || 0.0,
          category: category || '',
          available: available !== false,
        })
        .returning()
        .get();
    } catch (err) {
      throw wrapDb(err);
    }
  }
}

module.exports = { DrizzleCatalogRepository };
