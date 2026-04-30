package app.marysia.skel.model;

/**
 * Wrapper-shared {@code items} resource consumed by the React frontend
 * via {@code ${BACKEND_URL}/api/items}.
 *
 * <p>Field layout mirrors the django-bolt skeleton's {@code Item} model
 * so a single {@code _shared/db.sqlite3} is interchangeable across the
 * Python and JVM backends.
 *
 * <p>Jackson serialises the camelCase Java fields to snake_case JSON
 * keys ({@code is_completed}, {@code category_id}, {@code created_at},
 * {@code updated_at}) because
 * {@code spring.jackson.property-naming-strategy=SNAKE_CASE} is set
 * globally in {@code application.properties}.
 */
public record Item(
    Long id,
    String name,
    String description,
    boolean isCompleted,
    Long categoryId,
    String createdAt,
    String updatedAt
) {
}
