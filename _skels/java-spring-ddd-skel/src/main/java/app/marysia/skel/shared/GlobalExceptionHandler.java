package app.marysia.skel.shared;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Maps domain + framework exceptions into the {@code {detail, status}}
 * JSON body shape every dev_skel backend honours.
 *
 * <p>This is the single cross-cutting error funnel for the DDD layout.
 * Each resource's controller stays thin — it throws
 * {@link DomainException} subclasses from the service-layer surface and
 * lets this handler take care of translation. The legacy per-controller
 * {@code @ExceptionHandler} blocks (one per controller in the previous
 * layout) collapse into the single advice you see here.
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(DomainException.class)
    public ResponseEntity<Map<String, Object>> handleDomain(DomainException ex) {
        return body(ex.status(), ex.getMessage());
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<Map<String, Object>> handleMalformedJson(HttpMessageNotReadableException ex) {
        return body(HttpStatus.BAD_REQUEST,
            "malformed request body: " + rootMessage(ex));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handleBeanValidation(MethodArgumentNotValidException ex) {
        String detail = ex.getBindingResult().getFieldErrors().stream()
            .findFirst()
            .map(fe -> fe.getField() + ": " + fe.getDefaultMessage())
            .orElse("validation failed");
        return body(HttpStatus.BAD_REQUEST, detail);
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, Object>> handleIllegalArgument(IllegalArgumentException ex) {
        return body(HttpStatus.BAD_REQUEST,
            ex.getMessage() == null ? "bad request" : ex.getMessage());
    }

    /**
     * Catch-all for unexpected runtime exceptions. Returns the standard
     * 500 body shape so the frontend can render a sensible error
     * message instead of the default Spring whitelabel page.
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, Object>> handleAny(Exception ex) {
        return body(HttpStatus.INTERNAL_SERVER_ERROR,
            ex.getMessage() == null ? ex.getClass().getSimpleName() : ex.getMessage());
    }

    private static ResponseEntity<Map<String, Object>> body(HttpStatus status, String detail) {
        // LinkedHashMap keeps the JSON keys in {detail, status} order to
        // match the contract every other dev_skel backend produces.
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("detail", detail);
        payload.put("status", status.value());
        return ResponseEntity.status(status).body(payload);
    }

    private static String rootMessage(Throwable t) {
        Throwable cur = t;
        while (cur.getCause() != null && cur.getCause() != cur) {
            cur = cur.getCause();
        }
        return cur.getMessage() == null ? t.getClass().getSimpleName() : cur.getMessage();
    }
}
