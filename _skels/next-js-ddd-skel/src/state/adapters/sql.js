/**
 * Drizzle-backed implementation of StateRepository.
 */

const { eq, and } = require('drizzle-orm');
const { reactState } = require('../../lib/schema');

class DrizzleStateRepository {
  constructor(db) {
    if (!db) throw new Error('DrizzleStateRepository requires a Drizzle db handle');
    this.db = db;
  }

  listForUser(userId) {
    const rows = this.db
      .select({ key: reactState.key, value: reactState.value })
      .from(reactState)
      .where(eq(reactState.user_id, Number(userId)))
      .all();

    const out = {};
    for (const row of rows) out[row.key] = row.value;
    return out;
  }

  upsertForUser(userId, key, value) {
    const now = new Date();
    const uid = Number(userId);
    this.db
      .insert(reactState)
      .values({ user_id: uid, key, value, updated_at: now })
      .onConflictDoUpdate({
        target: [reactState.user_id, reactState.key],
        set: { value, updated_at: now },
      })
      .run();
    return { key, value, updated_at: now };
  }

  deleteForUser(userId, key) {
    this.db
      .delete(reactState)
      .where(and(eq(reactState.user_id, Number(userId)), eq(reactState.key, key)))
      .run();
  }
}

module.exports = { DrizzleStateRepository };
