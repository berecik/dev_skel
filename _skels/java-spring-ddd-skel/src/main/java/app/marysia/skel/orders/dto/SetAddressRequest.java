package app.marysia.skel.orders.dto;

/**
 * Request body for {@code PUT /api/orders/{id}/address}. The
 * {@code zipCode} field maps to the {@code zip_code} snake_case JSON
 * key via the global Jackson naming strategy.
 */
public record SetAddressRequest(
    String street,
    String city,
    String zipCode,
    String phone,
    String notes
) {
}
