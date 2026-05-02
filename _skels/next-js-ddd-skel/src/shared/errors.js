/**
 * Domain error type used by every service in the skeleton.
 *
 * Services throw `DomainError` instances (or one of the convenience
 * factories like `DomainError.notFound("...")`) whenever they need to
 * surface a known failure mode. Routes catch these in `wrapResponse`
 * and translate the `kind` field into the matching HTTP status. This
 * keeps services framework-agnostic: they never reach for `Response`,
 * `NextResponse`, or any HTTP detail.
 */

const KINDS = ['NotFound', 'Conflict', 'Validation', 'Unauthorized', 'Forbidden', 'Other'];

class DomainError extends Error {
  /**
   * @param {string} kind  one of: NotFound | Conflict | Validation |
   *                       Unauthorized | Forbidden | Other.
   * @param {string} message human-readable detail; surfaces verbatim
   *                       in the JSON `error` field.
   */
  constructor(kind, message) {
    super(message);
    this.name = 'DomainError';
    this.kind = KINDS.includes(kind) ? kind : 'Other';
  }

  static notFound(message = 'Not found') {
    return new DomainError('NotFound', message);
  }
  static conflict(message = 'Conflict') {
    return new DomainError('Conflict', message);
  }
  static validation(message = 'Validation failed') {
    return new DomainError('Validation', message);
  }
  static unauthorized(message = 'Unauthorized') {
    return new DomainError('Unauthorized', message);
  }
  static forbidden(message = 'Forbidden') {
    return new DomainError('Forbidden', message);
  }
  static other(message = 'Internal server error') {
    return new DomainError('Other', message);
  }
}

/**
 * Translate a low-level driver / Drizzle error into a `DomainError`.
 * The two cases we recognise are unique-constraint violations (return
 * `Conflict`) and JSON-body parse errors (return `Validation`). Every
 * other error is wrapped as `Other` so callers can keep a uniform
 * try/catch shape.
 */
function wrapDb(err) {
  if (err instanceof DomainError) return err;
  if (err instanceof SyntaxError) {
    return DomainError.validation('Invalid JSON body');
  }
  const msg = err && err.message ? String(err.message) : '';
  if (
    msg.includes('UNIQUE constraint failed') ||
    msg.includes('duplicate key value') ||
    msg.includes('violates unique constraint')
  ) {
    return DomainError.conflict('Resource already exists');
  }
  return DomainError.other(msg || 'Internal server error');
}

module.exports = { DomainError, wrapDb, KINDS };
