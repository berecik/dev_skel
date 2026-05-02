/**
 * HTTP route handlers for /api/items.
 *
 * Each handler is a `(request, ctx) => Response`. The composition
 * root in `src/app/api/items/**` builds the service and wraps every
 * handler with `wrapResponse` so thrown DomainErrors become JSON
 * responses with the right status.
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

function getList(service, deps) {
  return async (request) => {
    await requireAuth(request, deps);
    const rows = service.list();
    return NextResponse.json(rows);
  };
}

function postCreate(service, deps) {
  return async (request) => {
    const user = await requireAuth(request, deps);
    const body = await readJsonBody(request);
    const ownerId = user && user.sub ? Number(user.sub) : null;
    const created = service.create({
      name: body.name,
      description: body.description,
      is_completed: body.is_completed,
      category_id: body.category_id,
      owner_id: ownerId,
    });
    return NextResponse.json(created, { status: 201 });
  };
}

function getOne(service, deps) {
  return async (request, ctx) => {
    await requireAuth(request, deps);
    const params = await ctx.params;
    const row = service.get(params.id);
    return NextResponse.json(row);
  };
}

function patchUpdate(service, deps) {
  return async (request, ctx) => {
    await requireAuth(request, deps);
    const params = await ctx.params;
    const body = await readJsonBody(request);
    const updated = service.update(params.id, body);
    return NextResponse.json(updated);
  };
}

function deleteOne(service, deps) {
  return async (request, ctx) => {
    await requireAuth(request, deps);
    const params = await ctx.params;
    service.delete(params.id);
    return new NextResponse(null, { status: 204 });
  };
}

function postComplete(service, deps) {
  return async (request, ctx) => {
    await requireAuth(request, deps);
    const params = await ctx.params;
    const updated = service.complete(params.id);
    return NextResponse.json(updated);
  };
}

module.exports = { getList, postCreate, getOne, patchUpdate, deleteOne, postComplete };
