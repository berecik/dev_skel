package app.marysia.skel.items.dto;

/**
 * Request body for {@code POST /api/items}. Jackson maps the incoming
 * snake_case JSON keys ({@code is_completed}, {@code category_id})
 * onto these camelCase fields because of the global {@code SNAKE_CASE}
 * naming strategy in {@code application.properties}.
 */
public record NewItemRequest(
    String name,
    String description,
    Boolean isCompleted,
    Long categoryId
) {
}
