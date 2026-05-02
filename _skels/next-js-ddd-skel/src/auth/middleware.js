/**
 * `requireAuth` — JWT bearer-token guard used by every protected route.
 *
 * The function returns the decoded principal on success or throws a
 * `DomainError.unauthorized(...)` on failure. The matching HTTP
 * conversion (401 + `{ error: ... }`) lives in `shared/httpx.js`'s
 * `wrapResponse` HOF, which is what the route files actually use to
 * shield handlers.
 *
 * Optionally accepts a `userRepository` in `deps` so callers can
 * resolve the authenticated principal to a full user row when they
 * need more than just the JWT claims (notably the auth/login flow).
 * Most routes only need the JWT claims and pass `deps = {}`.
 */

const { authenticateRequest } = require('../lib/auth');
const { DomainError } = require('../shared/errors');

/**
 * @param {Request} request
 * @param {{ userRepository?: object }} [deps]
 * @returns {Promise<object>} decoded JWT payload (`{ sub, username, ... }`)
 */
async function requireAuth(request, deps = {}) {
  let payload;
  try {
    payload = await authenticateRequest(request);
  } catch (err) {
    throw DomainError.unauthorized(err && err.message ? err.message : 'Unauthorized');
  }
  // If the caller supplied a user repository AND wants the full user
  // row, resolve it. We only do this when deps.resolveUser === true so
  // hot-path routes don't pay a DB lookup per request.
  if (deps && deps.resolveUser && deps.userRepository && payload && payload.sub) {
    const id = Number(payload.sub);
    const user = deps.userRepository.findById(id);
    if (!user) {
      throw DomainError.unauthorized('Token references unknown user');
    }
    return { ...payload, user };
  }
  return payload;
}

module.exports = { requireAuth };
