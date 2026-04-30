package app.marysia.skel.model;

/**
 * Wrapper-shared {@code catalog_items} resource representing a product
 * that can be added to an order.
 *
 * <p>Jackson serialises the camelCase Java fields to snake_case JSON
 * keys because
 * {@code spring.jackson.property-naming-strategy=SNAKE_CASE} is set
 * globally in {@code application.properties}.
 */
public record CatalogItem(
    Long id,
    String name,
    String description,
    double price,
    String category,
    boolean available
) {
}
