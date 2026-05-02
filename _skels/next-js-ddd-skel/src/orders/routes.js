/**
 * HTTP route handlers for /api/orders/*.
 *
 * The orders aggregate has the deepest URL tree in the skel; this
 * file exports a flat set of (request, ctx) handlers that the
 * App Router files thin-wire onto each path.
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

function principalUserId(principal) {
  return principal && principal.sub ? Number(principal.sub) : null;
}

function getList(service, deps) {
  return async (request) => {
    const principal = await requireAuth(request, deps);
    return NextResponse.json(service.list(principalUserId(principal)));
  };
}

function postCreate(service, deps) {
  return async (request) => {
    const principal = await requireAuth(request, deps);
    const created = service.draft(principalUserId(principal));
    return NextResponse.json(created, { status: 201 });
  };
}

function getOne(service, deps) {
  return async (request, ctx) => {
    const principal = await requireAuth(request, deps);
    const params = await ctx.params;
    return NextResponse.json(service.get(principalUserId(principal), params.id));
  };
}

function postAddLine(service, deps) {
  return async (request, ctx) => {
    const principal = await requireAuth(request, deps);
    const params = await ctx.params;
    const body = await readJsonBody(request);
    const line = service.addLine(principalUserId(principal), params.id, {
      catalog_item_id: body.catalog_item_id,
      quantity: body.quantity,
    });
    return NextResponse.json(line, { status: 201 });
  };
}

function deleteLine(service, deps) {
  return async (request, ctx) => {
    const principal = await requireAuth(request, deps);
    const params = await ctx.params;
    service.removeLine(principalUserId(principal), params.id, params.lineId);
    return new NextResponse(null, { status: 204 });
  };
}

function putAddress(service, deps) {
  return async (request, ctx) => {
    const principal = await requireAuth(request, deps);
    const params = await ctx.params;
    const body = await readJsonBody(request);
    const result = service.setAddress(principalUserId(principal), params.id, {
      street: body.street,
      city: body.city,
      zip_code: body.zip_code,
      phone: body.phone,
      notes: body.notes,
    });
    return NextResponse.json(result);
  };
}

function postSubmit(service, deps) {
  return async (request, ctx) => {
    const principal = await requireAuth(request, deps);
    const params = await ctx.params;
    return NextResponse.json(service.submit(principalUserId(principal), params.id));
  };
}

function postApprove(service, deps) {
  return async (request, ctx) => {
    await requireAuth(request, deps);
    const params = await ctx.params;
    const body = await readJsonBody(request);
    return NextResponse.json(service.approve(params.id, body || {}));
  };
}

function postReject(service, deps) {
  return async (request, ctx) => {
    await requireAuth(request, deps);
    const params = await ctx.params;
    const body = await readJsonBody(request);
    return NextResponse.json(service.reject(params.id, body || {}));
  };
}

module.exports = {
  getList,
  postCreate,
  getOne,
  postAddLine,
  deleteLine,
  putAddress,
  postSubmit,
  postApprove,
  postReject,
};
