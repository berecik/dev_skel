/**
 * Abstract repository contract shared by every resource.
 *
 * JavaScript does not have interfaces, so we offer two ways to use
 * this:
 *
 *   1. `class FooRepository extends Repository {}` — gives concrete
 *      adapters a documented superclass and tooling-friendly
 *      structure. Methods are intentionally throwing stubs so a
 *      half-implemented adapter fails fast.
 *
 *   2. Duck-typed objects passed to `assertHasMethods(repo, [...])`
 *      — useful when an adapter wants to satisfy multiple repository
 *      protocols without multiple inheritance.
 *
 * The `AbstractUnitOfWork` stub is here for symmetry with the sister
 * DDD skels (Go / Rust / Python). Drizzle's better-sqlite3 driver is
 * synchronous and does not benefit from a UOW today, but having the
 * seam means a future Postgres switch can introduce real transaction
 * boundaries without touching every service.
 */

class Repository {
  /* eslint-disable no-unused-vars */
  async list() {
    throw new Error('Repository.list() not implemented');
  }
  async get(id) {
    throw new Error('Repository.get(id) not implemented');
  }
  async save(entity) {
    throw new Error('Repository.save(entity) not implemented');
  }
  async update(id, patch) {
    throw new Error('Repository.update(id, patch) not implemented');
  }
  async delete(id) {
    throw new Error('Repository.delete(id) not implemented');
  }
  /* eslint-enable no-unused-vars */
}

class AbstractUnitOfWork {
  async begin() {
    /* default: no-op */
  }
  async commit() {
    /* default: no-op */
  }
  async rollback() {
    /* default: no-op */
  }
}

/**
 * Throw if `repo` is missing one of the named methods. Lets a service
 * fail fast at composition time when an adapter is half-built rather
 * than mid-request.
 */
function assertHasMethods(repo, names, label = 'repository') {
  if (!repo || typeof repo !== 'object') {
    throw new Error(`${label} must be an object, got ${typeof repo}`);
  }
  for (const name of names) {
    if (typeof repo[name] !== 'function') {
      throw new Error(`${label} is missing required method: ${name}()`);
    }
  }
}

module.exports = { Repository, AbstractUnitOfWork, assertHasMethods };
