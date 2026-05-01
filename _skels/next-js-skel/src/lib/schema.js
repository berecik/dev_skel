/**
 * Drizzle ORM schema for the Next.js backend skeleton.
 *
 * All datetime columns use `integer({ mode: "timestamp" })` so Drizzle
 * converts to/from JavaScript `Date` instances automatically (stored as
 * unix epoch seconds in SQLite). When such a row is serialised through
 * `Response.json(...)`, the `Date.toJSON()` method emits an ISO 8601
 * string -- which is exactly the wire format the React + Flutter
 * cross-stack tests expect for `created_at` / `updated_at`.
 *
 * Boolean columns use `integer({ mode: "boolean" })` so handlers and
 * tests see real `true` / `false` values instead of 0/1.
 *
 * JS field names are kept snake_case to match the column names so that
 * `db.select().from(table)` rows can be returned directly via
 * `NextResponse.json(...)` without manual remapping.
 */

const { sqliteTable, integer, text, real, uniqueIndex } = require('drizzle-orm/sqlite-core');

const users = sqliteTable('users', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  username: text('username').notNull().unique(),
  email: text('email').unique(),
  password_hash: text('password_hash').notNull(),
  created_at: integer('created_at', { mode: 'timestamp' }).$defaultFn(() => new Date()),
});

const categories = sqliteTable('categories', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  name: text('name').notNull().unique(),
  description: text('description'),
  created_at: integer('created_at', { mode: 'timestamp' }).$defaultFn(() => new Date()),
  updated_at: integer('updated_at', { mode: 'timestamp' }).$defaultFn(() => new Date()),
});

const items = sqliteTable('items', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  name: text('name').notNull(),
  description: text('description'),
  is_completed: integer('is_completed', { mode: 'boolean' }).notNull().default(false),
  category_id: integer('category_id').references(() => categories.id, { onDelete: 'set null' }),
  owner_id: integer('owner_id'),
  created_at: integer('created_at', { mode: 'timestamp' }).$defaultFn(() => new Date()),
  updated_at: integer('updated_at', { mode: 'timestamp' }).$defaultFn(() => new Date()),
});

const reactState = sqliteTable(
  'react_state',
  {
    id: integer('id').primaryKey({ autoIncrement: true }),
    user_id: integer('user_id').notNull(),
    key: text('key').notNull(),
    value: text('value').notNull().default('""'),
    updated_at: integer('updated_at', { mode: 'timestamp' }).$defaultFn(() => new Date()),
  },
  (table) => ({
    user_key_unique: uniqueIndex('react_state_user_key_unique').on(table.user_id, table.key),
  }),
);

const catalogItems = sqliteTable('catalog_items', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  name: text('name').notNull(),
  description: text('description').default(''),
  price: real('price').notNull().default(0.0),
  category: text('category').default(''),
  available: integer('available', { mode: 'boolean' }).default(true),
});

const orders = sqliteTable('orders', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  user_id: integer('user_id').notNull().references(() => users.id),
  status: text('status').notNull().default('draft'),
  feedback: text('feedback'),
  wait_minutes: integer('wait_minutes'),
  created_at: integer('created_at', { mode: 'timestamp' }).$defaultFn(() => new Date()),
  updated_at: integer('updated_at', { mode: 'timestamp' }).$defaultFn(() => new Date()),
});

const orderLines = sqliteTable('order_lines', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  order_id: integer('order_id').notNull().references(() => orders.id, { onDelete: 'cascade' }),
  catalog_item_id: integer('catalog_item_id').notNull().references(() => catalogItems.id),
  quantity: integer('quantity').default(1),
  unit_price: real('unit_price').default(0.0),
});

const orderAddresses = sqliteTable('order_addresses', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  order_id: integer('order_id')
    .notNull()
    .unique()
    .references(() => orders.id, { onDelete: 'cascade' }),
  street: text('street').notNull(),
  city: text('city').notNull(),
  zip_code: text('zip_code').notNull(),
  phone: text('phone').default(''),
  notes: text('notes').default(''),
});

module.exports = {
  users,
  categories,
  items,
  reactState,
  catalogItems,
  orders,
  orderLines,
  orderAddresses,
};
