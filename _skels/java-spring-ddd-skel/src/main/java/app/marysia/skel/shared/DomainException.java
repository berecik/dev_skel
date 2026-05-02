package app.marysia.skel.shared;

import org.springframework.http.HttpStatus;

/**
 * Sentinel-style domain exception base used by every service in the
 * DDD layout.
 *
 * <p>Mirrors the {@code DomainError} enum used in the sister rust-actix
 * and rust-axum DDD skels and the {@code shared.Err*} sentinels in
 * go-ddd-skel: services throw a typed subclass instead of leaking raw
 * persistence exceptions; the {@link GlobalExceptionHandler} in this
 * package translates them into the canonical {@code {detail, status}}
 * JSON body shape every dev_skel backend honours.
 *
 * <p>The default mapping is:
 * <ul>
 *   <li>{@link NotFoundException} &rarr; 404</li>
 *   <li>{@link ConflictException} &rarr; 409</li>
 *   <li>{@link ValidationException} &rarr; 400</li>
 *   <li>{@link UnauthorizedException} &rarr; 401</li>
 * </ul>
 *
 * <p>The {@link #status()} accessor lets the handler short-circuit the
 * lookup — and lets bespoke subclasses (none today) override the
 * default mapping if they ever need to.
 */
public abstract class DomainException extends RuntimeException {

    private final HttpStatus status;

    protected DomainException(HttpStatus status, String message) {
        super(message);
        this.status = status;
    }

    public HttpStatus status() {
        return status;
    }
}
