package app.marysia.skel.shared;

import org.springframework.http.HttpStatus;

/**
 * Caller is not authenticated, or the token / credentials supplied are
 * invalid — translated to {@code 401 Unauthorized} by
 * {@link GlobalExceptionHandler}.
 */
public class UnauthorizedException extends DomainException {

    public UnauthorizedException(String message) {
        super(HttpStatus.UNAUTHORIZED, message);
    }
}
