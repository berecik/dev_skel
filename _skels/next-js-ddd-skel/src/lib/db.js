/**
 * SQLite database module — Drizzle ORM on top of better-sqlite3.
 *
 * Creates/opens the database at the path derived from DATABASE_URL
 * (via config.dbPath). Schema is defined in `./schema.js` (the single
 * source of truth for table definitions); on first call this module
 * also runs an idempotent `CREATE TABLE IF NOT EXISTS` bootstrap so a
 * fresh skeleton clone is self-bootstrapping with no separate migration
 * step.
 *
 * Datetime columns are declared as `integer({ mode: "timestamp" })` in
 * the schema, so the underlying physical type is INTEGER (unix epoch
 * seconds) and Drizzle yields JavaScript `Date` objects in/out.
 */

const { mkdirSync } = require('node:fs');
const { dirname, resolve, isAbsolute } = require('node:path');
const Database = require('better-sqlite3');
const { drizzle } = require('drizzle-orm/better-sqlite3');
const { sql } = require('drizzle-orm');
const { config } = require('../config');
const { seedDefaultAccounts } = require('./seed');

let _db = null;
let _sqlite = null;

/**
 * Ensure the directory for the database file exists.
 */
function ensureDir(filePath) {
  const absPath = isAbsolute(filePath) ? filePath : resolve(process.cwd(), filePath);
  mkdirSync(dirname(absPath), { recursive: true });
  return absPath;
}

/**
 * Idempotent schema bootstrap — emits CREATE TABLE IF NOT EXISTS for
 * every table declared in `schema.js`. Drizzle does not ship a runtime
 * migration helper for the better-sqlite3 driver, so this keeps the
 * skeleton self-bootstrapping just like the prior raw-SQL version.
 *
 * Datetime columns are INTEGER (unix epoch seconds) so they round-trip
 * through Drizzle's `mode: 'timestamp'` accessors.
 */
function initDb(db) {
  db.run(sql`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      email TEXT UNIQUE,
      password_hash TEXT NOT NULL,
      created_at INTEGER
    )
  `);

  db.run(sql`
    CREATE TABLE IF NOT EXISTS categories (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      description TEXT,
      created_at INTEGER,
      updated_at INTEGER
    )
  `);

  db.run(sql`
    CREATE TABLE IF NOT EXISTS items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      description TEXT,
      is_completed INTEGER NOT NULL DEFAULT 0,
      category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
      owner_id INTEGER,
      created_at INTEGER,
      updated_at INTEGER
    )
  `);

  db.run(sql`
    CREATE TABLE IF NOT EXISTS react_state (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      key TEXT NOT NULL,
      value TEXT NOT NULL DEFAULT '""',
      updated_at INTEGER,
      UNIQUE(user_id, key)
    )
  `);

  db.run(sql`
    CREATE TABLE IF NOT EXISTS catalog_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      description TEXT DEFAULT '',
      price REAL NOT NULL DEFAULT 0.0,
      category TEXT DEFAULT '',
      available INTEGER DEFAULT 1
    )
  `);

  db.run(sql`
    CREATE TABLE IF NOT EXISTS orders (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL REFERENCES users(id),
      status TEXT NOT NULL DEFAULT 'draft',
      feedback TEXT,
      wait_minutes INTEGER,
      created_at INTEGER,
      updated_at INTEGER
    )
  `);

  db.run(sql`
    CREATE TABLE IF NOT EXISTS order_lines (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
      catalog_item_id INTEGER NOT NULL REFERENCES catalog_items(id),
      quantity INTEGER DEFAULT 1,
      unit_price REAL DEFAULT 0.0
    )
  `);

  db.run(sql`
    CREATE TABLE IF NOT EXISTS order_addresses (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id) ON DELETE CASCADE,
      street TEXT NOT NULL,
      city TEXT NOT NULL,
      zip_code TEXT NOT NULL,
      phone TEXT DEFAULT '',
      notes TEXT DEFAULT ''
    )
  `);

  return db;
}

/**
 * Return the singleton Drizzle handle, creating it (and tables) on first call.
 * The Drizzle handle wraps a better-sqlite3 connection -- both pragma and
 * raw-SQL escape hatches remain available via the underlying client.
 */
function getDb() {
  if (_db) return _db;

  const dbPath = ensureDir(config.dbPath);
  _sqlite = new Database(dbPath);
  _sqlite.pragma('journal_mode = WAL');
  _sqlite.pragma('foreign_keys = ON');

  _db = drizzle(_sqlite);
  initDb(_db);
  seedDefaultAccounts(_db);
  return _db;
}

/**
 * For testing: create an in-memory Drizzle handle with the same schema.
 * Returns the Drizzle wrapper -- callers should use the schema-driven
 * query builder rather than reaching into the underlying better-sqlite3
 * client.
 */
function createTestDb() {
  const sqlite = new Database(':memory:');
  sqlite.pragma('foreign_keys = ON');
  const db = drizzle(sqlite);
  initDb(db);
  return db;
}

/**
 * Close the singleton database handle (useful for graceful shutdown).
 */
function closeDb() {
  if (_sqlite) {
    _sqlite.close();
    _sqlite = null;
    _db = null;
  }
}

module.exports = { getDb, initDb, createTestDb, closeDb };
