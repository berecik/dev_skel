package com.example.skel.controller;

import com.example.skel.controller.ItemController.ApiException;
import com.example.skel.model.Category;
import com.example.skel.security.AuthUser;
import com.example.skel.service.CategoryService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * Wrapper-shared {@code /api/categories} CRUD that the React frontend
 * consumes. Every endpoint requires a Bearer JWT — the
 * {@link com.example.skel.security.JwtAuthInterceptor} fronts every
 * route declared on this controller and rejects unauthenticated /
 * malformed-token requests with a JSON 401 body.
 *
 * <p>Categories are shared (not per-user) but auth-protected — any
 * authenticated user can CRUD them. Items reference categories via an
 * optional {@code category_id} FK.
 */
@RestController
@RequestMapping("/api/categories")
public class CategoryController {

    private final CategoryService categories;

    public CategoryController(CategoryService categories) {
        this.categories = categories;
    }

    @GetMapping
    public List<Category> list(@SuppressWarnings("unused") AuthUser user) {
        return categories.findAll();
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Category create(@SuppressWarnings("unused") AuthUser user,
                           @RequestBody CreateCategoryRequest body) {
        if (body == null || body.name() == null || body.name().isBlank()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "category name cannot be empty");
        }
        return categories.create(body.name(), body.description());
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
        return categories.update(id, body.name(), body.description())
            .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "category " + id + " not found"));
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@SuppressWarnings("unused") AuthUser user, @PathVariable long id) {
        if (!categories.delete(id)) {
            throw new ApiException(HttpStatus.NOT_FOUND, "category " + id + " not found");
        }
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
