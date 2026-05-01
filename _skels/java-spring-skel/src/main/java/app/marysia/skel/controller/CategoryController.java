package app.marysia.skel.controller;

import app.marysia.skel.controller.ItemController.ApiException;
import app.marysia.skel.model.Category;
import app.marysia.skel.repository.CategoryRepository;
import app.marysia.skel.security.AuthUser;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Wrapper-shared {@code /api/categories} CRUD that the React frontend
 * consumes. Every endpoint requires a Bearer JWT — the
 * {@link app.marysia.skel.security.JwtAuthInterceptor} fronts every
 * route declared on this controller and rejects unauthenticated /
 * malformed-token requests with a JSON 401 body.
 *
 * <p>Categories are shared (not per-user) but auth-protected — any
 * authenticated user can CRUD them. Items reference categories via an
 * optional {@code category_id} FK enforced at the entity level by
 * {@link app.marysia.skel.model.Item}'s {@code @ManyToOne}.
 */
@RestController
@RequestMapping("/api/categories")
public class CategoryController {

    private final CategoryRepository categories;

    public CategoryController(CategoryRepository categories) {
        this.categories = categories;
    }

    @GetMapping
    public List<Category> list(@SuppressWarnings("unused") AuthUser user) {
        return categories.findAllByOrderByIdAsc();
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Category create(@SuppressWarnings("unused") AuthUser user,
                           @RequestBody CreateCategoryRequest body) {
        if (body == null || body.name() == null || body.name().isBlank()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "category name cannot be empty");
        }
        Category c = new Category(body.name(), body.description());
        return categories.save(c);
    }

    @GetMapping("/{id}")
    public Category get(@SuppressWarnings("unused") AuthUser user, @PathVariable long id) {
        return categories.findById(id)
            .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "category " + id + " not found"));
    }

    @PutMapping("/{id}")
    public Category update(@SuppressWarnings("unused") AuthUser user,
                           @PathVariable long id,
                           @RequestBody CreateCategoryRequest body) {
        if (body == null || body.name() == null || body.name().isBlank()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "category name cannot be empty");
        }
        Optional<Category> found = categories.findById(id);
        if (found.isEmpty()) {
            throw new ApiException(HttpStatus.NOT_FOUND, "category " + id + " not found");
        }
        Category c = found.get();
        c.setName(body.name());
        c.setDescription(body.description());
        return categories.save(c);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@SuppressWarnings("unused") AuthUser user, @PathVariable long id) {
        if (!categories.existsById(id)) {
            throw new ApiException(HttpStatus.NOT_FOUND, "category " + id + " not found");
        }
        categories.deleteById(id);
    }

    /**
     * Request body for {@code POST /api/categories} and
     * {@code PUT /api/categories/{id}}.
     */
    public record CreateCategoryRequest(String name, String description) {
    }

    /**
     * Exception handler scoped to this controller — converts
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
