package com.example.skel.model;

/**
 * Wrapper-shared {@code orders} resource representing a customer order.
 * Named {@code OrderRecord} to avoid clashing with {@link java.util.Order}
 * (preview API in recent JDKs).
 *
 * <p>Jackson serialises the camelCase Java fields to snake_case JSON
 * keys because
 * {@code spring.jackson.property-naming-strategy=SNAKE_CASE} is set
 * globally in {@code application.properties}.
 */
public record OrderRecord(
    Long id,
    long userId,
    String status,
    String createdAt,
    String submittedAt,
    Integer waitMinutes,
    String feedback
) {
}
