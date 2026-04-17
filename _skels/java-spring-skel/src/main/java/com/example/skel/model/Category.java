package com.example.skel.model;

/**
 * Wrapper-shared {@code categories} resource consumed by the React
 * frontend via {@code ${BACKEND_URL}/api/categories}.
 *
 * <p>Field layout mirrors the django-bolt skeleton's {@code Category}
 * model so a single {@code _shared/db.sqlite3} is interchangeable
 * across the Python and JVM backends.
 *
 * <p>Jackson serialises the camelCase Java fields to snake_case JSON
 * keys ({@code created_at}, {@code updated_at}) because
 * {@code spring.jackson.property-naming-strategy=SNAKE_CASE} is set
 * globally in {@code application.properties}.
 */
public record Category(
    Long id,
    String name,
    String description,
    String createdAt,
    String updatedAt
) {
}
