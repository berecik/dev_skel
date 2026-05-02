/**
 * Per-route composition helper.
 *
 * App Router files use this to lazily build a per-resource service +
 * shared `deps` (currently just the user repository, used by
 * `requireAuth` for principal resolution). The `getDb()` singleton
 * already memoizes the underlying connection; this helper memoizes
 * the constructed service + deps so we don't allocate them on every
 * request hot path.
 */

const { getDb } = require('../lib/db');
const { buildUserRepository } = require('../auth/depts');

// One slot per (db handle, builder) pair. The dev-mode hot-reload
// can rebuild the singleton db; we re-wire when that happens.
const _serviceCache = new Map();
let _cachedDeps = null;
let _depsDb = null;

function getDeps() {
  const db = getDb();
  if (_cachedDeps && _depsDb === db) return _cachedDeps;
  _depsDb = db;
  _cachedDeps = { userRepository: buildUserRepository(db) };
  return _cachedDeps;
}

/**
 * Memoize a service-builder against the singleton `db` handle.
 *
 *   const items = wireService(buildItemsService);
 *   export const GET = wrapResponse((req) => routes.getList(items(), getDeps())(req));
 */
function wireService(builder) {
  return function () {
    const db = getDb();
    const cached = _serviceCache.get(builder);
    if (cached && cached.db === db) return cached.svc;
    const svc = builder(db);
    _serviceCache.set(builder, { db, svc });
    return svc;
  };
}

module.exports = { getDeps, wireService };
