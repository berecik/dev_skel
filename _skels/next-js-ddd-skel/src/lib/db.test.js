const { describe, it } = require('node:test');
const assert = require('node:assert');
const { eq } = require('drizzle-orm');
const { createTestDb } = require('./db');
const { users, items, categories } = require('./schema');

describe('db module', () => {
  it('createTestDb creates users and items tables', () => {
    const db = createTestDb();
    const sqlite = db.$client;

    const tables = sqlite
      .prepare("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
      .all()
      .map((r) => r.name);

    assert.ok(tables.includes('users'), 'users table should exist');
    assert.ok(tables.includes('items'), 'items table should exist');
    sqlite.close();
  });

  it('can insert and query items via Drizzle', () => {
    const db = createTestDb();

    const inserted = db
      .insert(items)
      .values({ name: 'Test Item', description: 'A test item', is_completed: false })
      .returning()
      .get();
    assert.ok(inserted.id > 0, 'should get an insert id');

    const row = db.select().from(items).where(eq(items.id, inserted.id)).get();
    assert.strictEqual(row.name, 'Test Item');
    assert.strictEqual(row.description, 'A test item');
    assert.strictEqual(row.is_completed, false);
    db.$client.close();
  });

  it('can insert and query users via Drizzle', () => {
    const db = createTestDb();

    const inserted = db
      .insert(users)
      .values({ username: 'alice', email: 'alice@example.com', password_hash: 'fakehash' })
      .returning()
      .get();
    assert.ok(inserted.id > 0, 'should get an insert id');

    const row = db.select().from(users).where(eq(users.id, inserted.id)).get();
    assert.strictEqual(row.username, 'alice');
    assert.strictEqual(row.email, 'alice@example.com');
    assert.strictEqual(row.password_hash, 'fakehash');
    db.$client.close();
  });

  it('enforces unique username constraint', () => {
    const db = createTestDb();

    db.insert(users)
      .values({ username: 'bob', email: 'bob@example.com', password_hash: 'hash1' })
      .run();

    assert.throws(
      () =>
        db
          .insert(users)
          .values({ username: 'bob', email: 'bob2@example.com', password_hash: 'hash2' })
          .run(),
      /UNIQUE constraint failed/,
    );
    db.$client.close();
  });

  it('items default is_completed to false', () => {
    const db = createTestDb();

    db.insert(items).values({ name: 'Simple Item' }).run();
    const row = db.select().from(items).where(eq(items.name, 'Simple Item')).get();
    assert.strictEqual(row.is_completed, false);
    db.$client.close();
  });

  it('createTestDb creates categories table', () => {
    const db = createTestDb();
    const sqlite = db.$client;

    const tables = sqlite
      .prepare("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
      .all()
      .map((r) => r.name);

    assert.ok(tables.includes('categories'), 'categories table should exist');
    sqlite.close();
  });

  it('can insert and query categories', () => {
    const db = createTestDb();

    const inserted = db
      .insert(categories)
      .values({ name: 'Books', description: 'Book-related items' })
      .returning()
      .get();
    assert.ok(inserted.id > 0, 'should get an insert id');

    const row = db.select().from(categories).where(eq(categories.id, inserted.id)).get();
    assert.strictEqual(row.name, 'Books');
    assert.strictEqual(row.description, 'Book-related items');
    db.$client.close();
  });

  it('enforces unique category name constraint', () => {
    const db = createTestDb();

    db.insert(categories).values({ name: 'Books', description: 'First' }).run();

    assert.throws(
      () => db.insert(categories).values({ name: 'Books', description: 'Second' }).run(),
      /UNIQUE constraint failed/,
    );
    db.$client.close();
  });

  it('items can reference a category', () => {
    const db = createTestDb();

    const cat = db
      .insert(categories)
      .values({ name: 'Tools', description: 'Tool items' })
      .returning()
      .get();

    const item = db
      .insert(items)
      .values({ name: 'Hammer', category_id: cat.id })
      .returning()
      .get();

    const row = db.select().from(items).where(eq(items.id, item.id)).get();
    assert.strictEqual(row.name, 'Hammer');
    assert.strictEqual(row.category_id, cat.id);
    db.$client.close();
  });

  it('items category_id defaults to null', () => {
    const db = createTestDb();

    db.insert(items).values({ name: 'No Category Item' }).run();
    const row = db.select().from(items).where(eq(items.name, 'No Category Item')).get();
    assert.strictEqual(row.category_id, null);
    db.$client.close();
  });
});