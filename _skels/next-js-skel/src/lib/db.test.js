const { describe, it } = require('node:test');
const assert = require('node:assert');
const Database = require('better-sqlite3');
const { initDb } = require('./db');

describe('db module', () => {
  it('initDb creates users and items tables', () => {
    const db = new Database(':memory:');
    initDb(db);

    const tables = db
      .prepare("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
      .all()
      .map((r) => r.name);

    assert.ok(tables.includes('users'), 'users table should exist');
    assert.ok(tables.includes('items'), 'items table should exist');
    db.close();
  });

  it('can insert and query items', () => {
    const db = new Database(':memory:');
    initDb(db);

    const stmt = db.prepare(
      'INSERT INTO items (name, description, is_completed) VALUES (?, ?, ?)'
    );
    const result = stmt.run('Test Item', 'A test item', 0);
    assert.ok(result.lastInsertRowid > 0, 'should get an insert id');

    const row = db.prepare('SELECT * FROM items WHERE id = ?').get(result.lastInsertRowid);
    assert.strictEqual(row.name, 'Test Item');
    assert.strictEqual(row.description, 'A test item');
    assert.strictEqual(row.is_completed, 0);
    db.close();
  });

  it('can insert and query users', () => {
    const db = new Database(':memory:');
    initDb(db);

    const stmt = db.prepare(
      'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)'
    );
    const result = stmt.run('alice', 'alice@example.com', 'fakehash');
    assert.ok(result.lastInsertRowid > 0, 'should get an insert id');

    const row = db.prepare('SELECT * FROM users WHERE id = ?').get(result.lastInsertRowid);
    assert.strictEqual(row.username, 'alice');
    assert.strictEqual(row.email, 'alice@example.com');
    assert.strictEqual(row.password_hash, 'fakehash');
    db.close();
  });

  it('enforces unique username constraint', () => {
    const db = new Database(':memory:');
    initDb(db);

    const stmt = db.prepare(
      'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)'
    );
    stmt.run('bob', 'bob@example.com', 'hash1');

    assert.throws(
      () => stmt.run('bob', 'bob2@example.com', 'hash2'),
      /UNIQUE constraint failed/
    );
    db.close();
  });

  it('items default is_completed to 0', () => {
    const db = new Database(':memory:');
    initDb(db);

    db.prepare('INSERT INTO items (name) VALUES (?)').run('Simple Item');
    const row = db.prepare('SELECT * FROM items WHERE name = ?').get('Simple Item');
    assert.strictEqual(row.is_completed, 0);
    db.close();
  });

  it('initDb creates categories table', () => {
    const db = new Database(':memory:');
    initDb(db);

    const tables = db
      .prepare("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
      .all()
      .map((r) => r.name);

    assert.ok(tables.includes('categories'), 'categories table should exist');
    db.close();
  });

  it('can insert and query categories', () => {
    const db = new Database(':memory:');
    initDb(db);

    const stmt = db.prepare(
      'INSERT INTO categories (name, description) VALUES (?, ?)'
    );
    const result = stmt.run('Books', 'Book-related items');
    assert.ok(result.lastInsertRowid > 0, 'should get an insert id');

    const row = db.prepare('SELECT * FROM categories WHERE id = ?').get(result.lastInsertRowid);
    assert.strictEqual(row.name, 'Books');
    assert.strictEqual(row.description, 'Book-related items');
    db.close();
  });

  it('enforces unique category name constraint', () => {
    const db = new Database(':memory:');
    initDb(db);

    const stmt = db.prepare(
      'INSERT INTO categories (name, description) VALUES (?, ?)'
    );
    stmt.run('Books', 'First');

    assert.throws(
      () => stmt.run('Books', 'Second'),
      /UNIQUE constraint failed/
    );
    db.close();
  });

  it('items can reference a category', () => {
    const db = new Database(':memory:');
    db.pragma('foreign_keys = ON');
    initDb(db);

    const catResult = db.prepare(
      'INSERT INTO categories (name, description) VALUES (?, ?)'
    ).run('Tools', 'Tool items');

    const itemResult = db.prepare(
      'INSERT INTO items (name, category_id) VALUES (?, ?)'
    ).run('Hammer', catResult.lastInsertRowid);

    const row = db.prepare('SELECT * FROM items WHERE id = ?').get(itemResult.lastInsertRowid);
    assert.strictEqual(row.name, 'Hammer');
    assert.strictEqual(row.category_id, Number(catResult.lastInsertRowid));
    db.close();
  });

  it('items category_id defaults to null', () => {
    const db = new Database(':memory:');
    initDb(db);

    db.prepare('INSERT INTO items (name) VALUES (?)').run('No Category Item');
    const row = db.prepare('SELECT * FROM items WHERE name = ?').get('No Category Item');
    assert.strictEqual(row.category_id, null);
    db.close();
  });
});
