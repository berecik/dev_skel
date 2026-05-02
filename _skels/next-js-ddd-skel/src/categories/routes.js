/**
 * HTTP route handlers for /api/categories.
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
    return NextResponse.json(service.list());
  };
}

function postCreate(service, deps) {
  return async (request) => {
    await requireAuth(request, deps);
    const body = await readJsonBody(request);
    const created = service.create({ name: body.name, description: body.description });
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

function putUpdate(service, deps) {
  return async (request, ctx) => {
    await requireAuth(request, deps);
    const params = await ctx.params;
    const body = await readJsonBody(request);
    return NextResponse.json(service.update(params.id, body));
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

module.exports = { getList, postCreate, getOne, putUpdate, deleteOne };
