/**
 * HTTP route handlers for /api/catalog.
 *
 * GET /api/catalog is anonymous; POST and GET-by-id require auth —
 * matching the existing flat-route behaviour.
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

function getList(service) {
  return async () => NextResponse.json(service.list());
}

function postCreate(service, deps) {
  return async (request) => {
    await requireAuth(request, deps);
    const body = await readJsonBody(request);
    const created = service.create({
      name: body.name,
      description: body.description,
      price: body.price,
      category: body.category,
      available: body.available,
    });
    return NextResponse.json(created, { status: 201 });
  };
}

function getOne(service, deps) {
  return async (request, ctx) => {
    await requireAuth(request, deps);
    const params = await ctx.params;
    return NextResponse.json(service.get(params.id));
  };
}

module.exports = { getList, postCreate, getOne };
