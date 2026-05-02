/**
 * HTTP helpers shared by every resource's `routes.js`.
 *
 * Routes use `wrapResponse(handler)` to get a uniform DomainError →
 * HTTP-status pipeline. The error envelope shape is
 *   { error: "<message>" }
 * which matches what the existing flat App Router routes emitted —
 * the cross-stack tests rely on this verbatim shape.
 */

const { NextResponse } = require('next/server');
const { DomainError, wrapDb } = require('./errors');

const STATUS_FOR_KIND = {
  NotFound: 404,
  Conflict: 409,
  Validation: 400,
  Unauthorized: 401,
  Forbidden: 403,
  Other: 500,
};

/**
 * Build a JSON error response with the wrapper-shared `{ error }`
 * envelope.
 */
function jsonError(status, detail) {
  return NextResponse.json({ error: String(detail) }, { status });
}

/**
 * Translate a `DomainError` into an HTTP response.
 *
 * Anything that is not a DomainError is wrapped via `wrapDb()` first
 * so unexpected failures still get a JSON envelope rather than a raw
 * stack trace.
 */
function toResponse(err) {
  const domain = err instanceof DomainError ? err : wrapDb(err);
  const status = STATUS_FOR_KIND[domain.kind] || 500;
  return jsonError(status, domain.message);
}

/**
 * Higher-order function used by every route file. Accepts an async
 * handler `(request, ctx) => Response` and returns a wrapper that
 * catches thrown DomainErrors and translates them to JSON responses.
 *
 * Routes therefore look like:
 *
 *   export const GET = wrapResponse(async (req) => { ... });
 */
function wrapResponse(handler) {
  return async function (request, ctx) {
    try {
      return await handler(request, ctx);
    } catch (err) {
      if (!(err instanceof DomainError)) {
        // Log unexpected errors so they show up in server output.
        console.error('Unhandled route error:', err);
      }
      return toResponse(err);
    }
  };
}

module.exports = { jsonError, toResponse, wrapResponse, STATUS_FOR_KIND };
