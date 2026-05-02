/**
 * Drizzle-backed implementation of OrderRepository.
 *
 * Knows how to query orders + order_lines + order_addresses + the
 * catalog item table (used by `addLine` to look up unit_price).
 */

const { eq, and, asc, desc } = require('drizzle-orm');
const { orders, orderLines, orderAddresses, catalogItems } = require('../../lib/schema');
const { wrapDb } = require('../../shared/errors');

class DrizzleOrderRepository {
  constructor(db) {
    if (!db) throw new Error('DrizzleOrderRepository requires a Drizzle db handle');
    this.db = db;
  }

  listForUser(userId) {
    return this.db
      .select()
      .from(orders)
      .where(eq(orders.user_id, Number(userId)))
      .orderBy(desc(orders.created_at))
      .all();
  }

  getRaw(orderId) {
    return (
      this.db.select().from(orders).where(eq(orders.id, Number(orderId))).get() || null
    );
  }

  getForUser(userId, orderId) {
    return (
      this.db
        .select()
        .from(orders)
        .where(and(eq(orders.id, Number(orderId)), eq(orders.user_id, Number(userId))))
        .get() || null
    );
  }

  listLines(orderId) {
    return this.db
      .select({
        id: orderLines.id,
        catalog_item_id: orderLines.catalog_item_id,
        quantity: orderLines.quantity,
        unit_price: orderLines.unit_price,
      })
      .from(orderLines)
      .where(eq(orderLines.order_id, Number(orderId)))
      .orderBy(asc(orderLines.id))
      .all();
  }

  getAddress(orderId) {
    return (
      this.db
        .select()
        .from(orderAddresses)
        .where(eq(orderAddresses.order_id, Number(orderId)))
        .get() || null
    );
  }

  getDetailForUser(userId, orderId) {
    const header = this.getForUser(userId, orderId);
    if (!header) return null;
    const lines = this.listLines(orderId);
    const address = this.getAddress(orderId);
    return { ...header, lines, address };
  }

  createDraft(userId) {
    try {
      return this.db
        .insert(orders)
        .values({ user_id: Number(userId), status: 'draft' })
        .returning()
        .get();
    } catch (err) {
      throw wrapDb(err);
    }
  }

  addLine(orderId, { catalog_item_id, quantity, unit_price }) {
    try {
      return this.db
        .insert(orderLines)
        .values({
          order_id: Number(orderId),
          catalog_item_id: Number(catalog_item_id),
          quantity: quantity ?? 1,
          unit_price: unit_price ?? 0.0,
        })
        .returning()
        .get();
    } catch (err) {
      throw wrapDb(err);
    }
  }

  getLine(orderId, lineId) {
    return (
      this.db
        .select()
        .from(orderLines)
        .where(
          and(eq(orderLines.id, Number(lineId)), eq(orderLines.order_id, Number(orderId))),
        )
        .get() || null
    );
  }

  removeLine(orderId, lineId) {
    const existing = this.getLine(orderId, lineId);
    if (!existing) return false;
    this.db.delete(orderLines).where(eq(orderLines.id, Number(lineId))).run();
    return true;
  }

  setAddress(orderId, addr) {
    const oid = Number(orderId);
    const values = {
      street: addr.street,
      city: addr.city,
      zip_code: addr.zip_code,
      phone: addr.phone || '',
      notes: addr.notes || '',
    };
    const existing = this.getAddress(oid);
    if (existing) {
      this.db.update(orderAddresses).set(values).where(eq(orderAddresses.order_id, oid)).run();
    } else {
      this.db.insert(orderAddresses).values({ order_id: oid, ...values }).run();
    }
  }

  updateStatus(orderId, status, patch = {}) {
    const oid = Number(orderId);
    const next = {
      status,
      updated_at: new Date(),
      ...(patch.feedback !== undefined ? { feedback: patch.feedback || null } : {}),
      ...(patch.wait_minutes !== undefined ? { wait_minutes: patch.wait_minutes ?? null } : {}),
    };
    return this.db.update(orders).set(next).where(eq(orders.id, oid)).returning().get() || null;
  }

  getCatalogItem(catalogItemId) {
    return (
      this.db
        .select()
        .from(catalogItems)
        .where(eq(catalogItems.id, Number(catalogItemId)))
        .get() || null
    );
  }
}

module.exports = { DrizzleOrderRepository };
