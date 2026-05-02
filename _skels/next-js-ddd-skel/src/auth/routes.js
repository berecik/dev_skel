/**
 * HTTP route handlers for /api/auth/{login,register}.
 *
 * Auth has no `requireAuth` guard at the entry — these endpoints are
 * the way clients obtain a token. Errors flow through DomainError →
 * `wrapResponse` like every other resource.
 */

const { NextResponse } = require('next/server');
const { DomainError } = require('../shared/errors');

async function readJsonBody(request) {
  try {
    return await request.json();
  } catch {
    throw DomainError.validation('Invalid JSON body');
  }
}

function postLogin(service) {
  return async (request) => {
    const body = await readJsonBody(request);
    const result = await service.login({
      username: body.username,
      password: body.password,
    });
    return NextResponse.json(result, { status: 200 });
  };
}

function postRegister(service) {
  return async (request) => {
    const body = await readJsonBody(request);
    const user = await service.register({
      username: body.username,
      email: body.email,
      password: body.password,
      password_confirm: body.password_confirm,
    });
    // Wire-format wraps the user under `user` — the previous flat
    // route emitted exactly this shape and the cross-stack tests
    // depend on it.
    return NextResponse.json({ user }, { status: 201 });
  };
}

module.exports = { postLogin, postRegister };
