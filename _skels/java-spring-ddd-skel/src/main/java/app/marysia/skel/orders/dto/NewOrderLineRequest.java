package app.marysia.skel.orders.dto;

/**
 * Request body for {@code POST /api/orders/{id}/lines}. The
 * {@code catalogItemId} field maps to the {@code catalog_item_id}
 * snake_case JSON key via the global Jackson naming strategy.
 */
public record NewOrderLineRequest(Long catalogItemId, Integer quantity) {
}
