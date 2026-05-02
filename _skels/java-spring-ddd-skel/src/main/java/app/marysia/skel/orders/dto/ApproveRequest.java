package app.marysia.skel.orders.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Request body for {@code POST /api/orders/{id}/approve}.
 *
 * <p>The pre-DDD record used the literal Java identifier
 * {@code wait_minutes} so Jackson would pick it up unchanged from the
 * snake_case JSON. The DDD record keeps the canonical Java
 * {@code waitMinutes} identifier and uses an explicit
 * {@link JsonProperty} so the wire format ({@code wait_minutes}) is
 * preserved without depending on the global naming strategy. (Records
 * disable Jackson's automatic property-naming-strategy translation on
 * accessors when there are matching parameter names, so we pin it
 * explicitly here.)
 */
public record ApproveRequest(
    @JsonProperty("wait_minutes") Integer waitMinutes,
    String feedback
) {
}
