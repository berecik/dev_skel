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
});
