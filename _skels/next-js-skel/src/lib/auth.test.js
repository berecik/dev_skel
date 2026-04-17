const { describe, it } = require('node:test');
const assert = require('node:assert');
const { hashPassword, verifyPassword, createToken, verifyToken } = require('./auth');

describe('auth module', () => {
  describe('password hashing', () => {
    it('hashPassword + verifyPassword round-trip succeeds', async () => {
      const password = 'my-secret-password';
      const hash = await hashPassword(password);

      assert.ok(hash, 'hash should be a non-empty string');
      assert.notStrictEqual(hash, password, 'hash should differ from plaintext');

      const valid = await verifyPassword(password, hash);
      assert.strictEqual(valid, true, 'correct password should verify');
    });

    it('verifyPassword rejects wrong password', async () => {
      const hash = await hashPassword('correct-password');
      const valid = await verifyPassword('wrong-password', hash);
      assert.strictEqual(valid, false, 'wrong password should not verify');
    });
  });

  describe('JWT tokens', () => {
    it('createToken + verifyToken round-trip succeeds', async () => {
      const payload = { sub: '42', username: 'testuser' };
      const token = await createToken(payload);

      assert.ok(token, 'token should be a non-empty string');
      assert.ok(token.split('.').length === 3, 'token should be a JWT (3 parts)');

      const decoded = await verifyToken(token);
      assert.strictEqual(decoded.sub, '42');
      assert.strictEqual(decoded.username, 'testuser');
    });

    it('verifyToken rejects garbage tokens', async () => {
      await assert.rejects(
        () => verifyToken('not.a.valid.token'),
        (err) => {
          assert.ok(err, 'should throw an error');
          return true;
        }
      );
    });

    it('verifyToken rejects tokens with wrong secret', async () => {
      // Create a token manually with the wrong secret
      const { SignJWT } = require('jose');
      const wrongSecret = new TextEncoder().encode('wrong-secret-key-for-testing');
      const badToken = await new SignJWT({ sub: '1' })
        .setProtectedHeader({ alg: 'HS256' })
        .setIssuer('devskel')
        .setExpirationTime('1h')
        .sign(wrongSecret);

      await assert.rejects(
        () => verifyToken(badToken),
        (err) => {
          assert.ok(err, 'should throw an error');
          return true;
        }
      );
    });
  });
});
