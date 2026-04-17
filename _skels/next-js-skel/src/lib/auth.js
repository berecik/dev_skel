/**
 * JWT + password utilities.
 *
 * Uses `jose` for JWT (works in all JS runtimes including Next.js edge)
 * and `bcryptjs` for password hashing.
 */

const { SignJWT, jwtVerify } = require('jose');
const bcrypt = require('bcryptjs');
const { config } = require('../config');

const SALT_ROUNDS = 12;

/**
 * Hash a plaintext password.
 */
async function hashPassword(password) {
  return bcrypt.hash(password, SALT_ROUNDS);
}

/**
 * Verify a plaintext password against a bcrypt hash.
 */
async function verifyPassword(password, hash) {
  return bcrypt.compare(password, hash);
}

/**
 * Encode the JWT secret as a Uint8Array for jose.
 */
function getSecretKey() {
  return new TextEncoder().encode(config.jwt.secret);
}

/**
 * Create a signed JWT with the given payload.
 */
async function createToken(payload) {
  const secret = getSecretKey();
  const token = await new SignJWT(payload)
    .setProtectedHeader({ alg: config.jwt.algorithm })
    .setIssuer(config.jwt.issuer)
    .setIssuedAt()
    .setExpirationTime(config.jwt.accessTtl + 's')
    .sign(secret);
  return token;
}

/**
 * Verify and decode a JWT. Returns the payload on success.
 * Throws on invalid/expired tokens.
 */
async function verifyToken(token) {
  const secret = getSecretKey();
  const { payload } = await jwtVerify(token, secret, {
    issuer: config.jwt.issuer,
  });
  return payload;
}

/**
 * Extract and verify the Bearer token from a request's Authorization header.
 * Returns the decoded JWT payload, or throws an Error with a message
 * suitable for a 401 response.
 */
async function authenticateRequest(request) {
  const authHeader = request.headers.get('authorization');
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    throw new Error('Missing or invalid Authorization header');
  }
  const token = authHeader.slice(7);
  return verifyToken(token);
}

module.exports = { hashPassword, verifyPassword, createToken, verifyToken, authenticateRequest };
