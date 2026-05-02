package app.marysia.skel.shared;

import org.springframework.http.HttpStatus;

/**
 * Uniqueness or state conflict — translated to {@code 409 Conflict} by
 * {@link GlobalExceptionHandler}.
 */
public class ConflictException extends DomainException {

    public ConflictException(String message) {
        super(HttpStatus.CONFLICT, message);
    }
}
