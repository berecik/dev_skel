/**
 * HTTP route handlers for /api/state/*.
 *
 * The pre-DDD wire format used `Authentication required` rather than
 * the generic `Unauthorized` for these handlers — preserved.
 */

const { NextResponse } = require('next/server');
const { DomainError } = require('../shared/errors');
const { requireAuth } = require('../auth/middleware');

async function readJsonBody(request) {
  try {
    return await request.json();
  } catch {
    throw DomainError.validation('Invalid JSON body');
  }
}

async function authForState(request, deps) {
  try {
    return await requireAuth(request, deps);
  } catch (err) {
    // The original flat route returned `Authentication required` —
    // preserve byte-identical message.
    if (err instanceof DomainError && err.kind === 'Unauthorized') {
      throw DomainError.unauthorized('Authentication required');
    }
    throw err;
  }
}

function getList(service, deps) {
  return async (request) => {
    const principal = await authForState(request, deps);
    const userId = principal && principal.sub ? Number(principal.sub) : 0;
    return NextResponse.json(service.list(userId));
  };
}

function putUpsert(service, deps) {
  return async (request, ctx) => {
    const principal = await authForState(request, deps);
    const userId = principal && principal.sub ? Number(principal.sub) : 0;
    const params = await ctx.params;
    const body = await readJsonBody(request);
    const value = body && body.value !== undefined ? body.value : '';
    return NextResponse.json(service.upsert(userId, params.key, value));
  };
}

function deleteOne(service, deps) {
  return async (request, ctx) => {
    const principal = await authForState(request, deps);
    const userId = principal && principal.sub ? Number(principal.sub) : 0;
    const params = await ctx.params;
    return NextResponse.json(service.delete(userId, params.key));
  };
}

module.exports = { getList, putUpsert, deleteOne };
