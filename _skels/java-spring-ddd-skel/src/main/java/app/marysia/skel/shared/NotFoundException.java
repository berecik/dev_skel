package app.marysia.skel.shared;

import org.springframework.http.HttpStatus;

/**
 * Resource lookup miss — translated to {@code 404 Not Found} by
 * {@link GlobalExceptionHandler}.
 */
public class NotFoundException extends DomainException {

    public NotFoundException(String message) {
        super(HttpStatus.NOT_FOUND, message);
    }
}
