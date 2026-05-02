/**
 * AuthService — register / login / me / refresh primitives.
 *
 * Depends on a `UserRepository`. Mirrors the previous flat
 * `/api/auth/login` and `/api/auth/register` behaviour byte-for-byte,
 * but throws DomainError on failure so the route layer is uniform.
 */

const { hashPassword, verifyPassword, createToken } = require('../lib/auth');
const { DomainError } = require('../shared/errors');
const { assertUserRepository } = require('../users/repository');

class AuthService {
  constructor(userRepository) {
    assertUserRepository(userRepository);
    this.users = userRepository;
  }

  async register({ username, email, password, password_confirm }) {
    if (!username || !password) {
      throw DomainError.validation('username and password are required');
    }
    if (password_confirm !== undefined && password !== password_confirm) {
      throw DomainError.validation('password and password_confirm do not match');
    }

    // Pre-check duplicates so we can surface a proper 409. The
    // adapter still rethrows the unique-constraint failure as
    // DomainError.conflict in case of a race.
    if (this.users.findByUsername(username)) {
      throw DomainError.conflict('Username already exists');
    }

    const password_hash = await hashPassword(password);
    const created = this.users.create({ username, email: email || null, password_hash });
    return {
      id: created.id,
      username: created.username,
      email: created.email,
    };
  }

  async login({ username, password }) {
    if (!username || !password) {
      throw DomainError.validation('username and password are required');
    }
    const user = this.users.findByLogin(username);
    if (!user) throw DomainError.unauthorized('Invalid credentials');

    const valid = await verifyPassword(password, user.password_hash);
    if (!valid) throw DomainError.unauthorized('Invalid credentials');

    const token = await createToken({
      sub: String(user.id),
      username: user.username,
    });
    return { access: token };
  }

  async me(payload) {
    if (!payload || !payload.sub) {
      throw DomainError.unauthorized('Missing principal');
    }
    const user = this.users.findById(Number(payload.sub));
    if (!user) throw DomainError.unauthorized('Token references unknown user');
    return { id: user.id, username: user.username, email: user.email };
  }

  async refresh(payload) {
    // Symmetric refresh — same shape as login. Kept as a separate
    // method so callers can swap in a real refresh-token flow later
    // without changing the route surface.
    if (!payload || !payload.sub) {
      throw DomainError.unauthorized('Missing principal');
    }
    const token = await createToken({
      sub: String(payload.sub),
      username: payload.username,
    });
    return { access: token };
  }
}

module.exports = { AuthService };
