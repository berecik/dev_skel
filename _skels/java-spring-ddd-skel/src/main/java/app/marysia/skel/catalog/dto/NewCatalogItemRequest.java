package app.marysia.skel.catalog.dto;

/**
 * Request body for {@code POST /api/catalog}. Validation lives in
 * {@code CatalogService}.
 */
public record NewCatalogItemRequest(
    String name,
    String description,
    Double price,
    String category,
    Boolean available
) {
}
