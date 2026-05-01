package app.marysia.skel.controller;

import app.marysia.skel.model.Category;
import app.marysia.skel.model.Item;
import app.marysia.skel.repository.CategoryRepository;
import app.marysia.skel.repository.ItemRepository;
import app.marysia.skel.security.AuthUser;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * Wrapper-shared {@code /api/items} CRUD that the React frontend
 * consumes. Every endpoint requires a Bearer JWT — the
 * {@link app.marysia.skel.security.JwtAuthInterceptor} fronts every
 * route declared on this controller and rejects unauthenticated /
 * malformed-token requests with a JSON 401 body.
 *
 * <p>{@link AuthUser} is injected by
 * {@link app.marysia.skel.security.AuthUserArgumentResolver}; we
 * accept it on every method so future tightening (e.g. ownership
 * scoping) does not need to add a new parameter to each controller.
 */
@RestController
@RequestMapping("/api/items")
public class ItemController {

    private final ItemRepository items;
    private final CategoryRepository categories;

    public ItemController(ItemRepository items, CategoryRepository categories) {
        this.items = items;
        this.categories = categories;
    }

    @GetMapping
    public List<Item> list(@SuppressWarnings("unused") AuthUser user) {
        return items.findAllByOrderByCreatedAtDescIdDesc();
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Item create(@SuppressWarnings("unused") AuthUser user,
                       @RequestBody CreateItemRequest body) {
        if (body == null || body.name() == null || body.name().isBlank()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "item name cannot be empty");
        }
        boolean isCompleted = body.isCompleted() != null && body.isCompleted();
        Category category = null;
        if (body.categoryId() != null) {
            category = categories.findById(body.categoryId())
                .orElseThrow(() -> new ApiException(HttpStatus.BAD_REQUEST,
                    "category " + body.categoryId() + " not found"));
        }
        Item item = new Item(body.name(), body.description(), isCompleted, category);
        return items.save(item);
    }

    @GetMapping("/{id}")
    public Item get(@SuppressWarnings("unused") AuthUser user, @PathVariable long id) {
        return items.findById(id)
            .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "item " + id + " not found"));
    }

    /**
     * {@code POST /api/items/{id}/complete} — flips
     * {@code is_completed=true} and returns the refreshed row.
     * Idempotent: completing an already-completed item is a no-op
     * that still returns 200.
     */
    @PostMapping("/{id}/complete")
    public Item complete(@SuppressWarnings("unused") AuthUser user, @PathVariable long id) {
        return items.findById(id)
            .map(item -> {
                item.setCompleted(true);
                return items.save(item);
            })
            .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "item " + id + " not found"));
    }

    /**
     * Request body for {@code POST /api/items}. Jackson maps the
     * incoming snake_case JSON keys onto the camelCase field names
     * because of the global {@code SNAKE_CASE} naming strategy in
     * {@code application.properties}.
     */
    public record CreateItemRequest(String name, String description, Boolean isCompleted, Long categoryId) {
    }

    /**
     * Local 4xx exception so the controllers can short-circuit with a
     * specific status code. Translated to a JSON body by
     * {@link GlobalExceptionHandler}.
     */
    public static class ApiException extends RuntimeException {
        private final HttpStatus status;

        public ApiException(HttpStatus status, String message) {
            super(message);
            this.status = status;
        }

        public HttpStatus status() {
            return status;
        }
    }

    /**
     * Default exception handler scoped to this controller — converts
     * {@link ApiException} into the same JSON 4xx body shape every
     * other dev_skel backend uses ({@code {detail, status}}).
     */
    @ExceptionHandler(ApiException.class)
    public ResponseEntity<Map<String, Object>> handleApiException(ApiException ex) {
        return ResponseEntity.status(ex.status()).body(Map.of(
            "detail", ex.getMessage(),
            "status", ex.status().value()
        ));
    }
}
