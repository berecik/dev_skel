package app.marysia.skel.shared;

import org.springframework.http.HttpStatus;

/**
 * Service-layer invariant violated — translated to {@code 400 Bad
 * Request} by {@link GlobalExceptionHandler}.
 */
public class ValidationException extends DomainException {

    public ValidationException(String message) {
        super(HttpStatus.BAD_REQUEST, message);
    }
}
