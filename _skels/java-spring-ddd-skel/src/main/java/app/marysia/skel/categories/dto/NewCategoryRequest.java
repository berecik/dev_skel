package app.marysia.skel.categories.dto;

/**
 * Request body for {@code POST /api/categories} and
 * {@code PUT /api/categories/{id}}. Validation lives in
 * {@code CategoryService} so the rules apply equally to either entry
 * point.
 */
public record NewCategoryRequest(String name, String description) {
}
