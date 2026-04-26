/**
 * SQLite database module using better-sqlite3.
 *
 * Creates/opens the database at the path derived from DATABASE_URL
 * (via config.dbPath). Tables are auto-created on first access.
 */

const { mkdirSync } = require('node:fs');
const { dirname, resolve, isAbsolute } = require('node:path');
const Database = require('better-sqlite3');
const { config } = require('../config');
const { seedDefaultAccounts } = require('./seed');

let _db = null;

/**
 * Ensure the directory for the database file exists.
 */
function ensureDir(filePath) {
  const absPath = isAbsolute(filePath) ? filePath : resolve(process.cwd(), filePath);
  mkdirSync(dirname(absPath), { recursive: true });
  return absPath;
}

/**
 * Create tables if they do not already exist.
 */
function initDb(db) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      email TEXT UNIQUE,
      password_hash TEXT NOT NULL,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
  `);

  db.exec(`
    CREATE TABLE IF NOT EXISTS categories (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      description TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
  `);

  db.exec(`
    CREATE TABLE IF NOT EXISTS items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      description TEXT,
      is_completed INTEGER NOT NULL DEFAULT 0,
      category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
      owner_id INTEGER,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
  `);

  db.exec(`
    CREATE TABLE IF NOT EXISTS react_state (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      key TEXT NOT NULL,
      value TEXT NOT NULL DEFAULT '""',
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(user_id, key)
    )
  `);

  return db;
}

/**
 * Return the singleton database handle, creating it (and tables) on first call.
 */
function getDb() {
  if (_db) return _db;

  const dbPath = ensureDir(config.dbPath);
  _db = new Database(dbPath);
  _db.pragma('journal_mode = WAL');
  _db.pragma('foreign_keys = ON');
  initDb(_db);
  seedDefaultAccounts(_db);
  return _db;
}

/**
 * For testing: create an in-memory database with the same schema.
 */
function createTestDb() {
  const db = new Database(':memory:');
  db.pragma('foreign_keys = ON');
  return initDb(db);
}

/**
 * Close the singleton database handle (useful for graceful shutdown).
 */
function closeDb() {
  if (_db) {
    _db.close();
    _db = null;
  }
}

module.exports = { getDb, initDb, createTestDb, closeDb };
