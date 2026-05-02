package app.marysia.skel.orders.dto;

/**
 * Request body for {@code POST /api/orders/{id}/reject}.
 */
public record RejectRequest(String feedback) {
}
