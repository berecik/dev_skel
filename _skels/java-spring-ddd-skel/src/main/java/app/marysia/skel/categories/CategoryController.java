package app.marysia.skel.categories;

import app.marysia.skel.auth.AuthUser;
import app.marysia.skel.categories.dto.NewCategoryRequest;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * Wrapper-shared {@code /api/categories} CRUD that the React frontend
 * consumes. Every endpoint requires a Bearer JWT — the
 * {@link app.marysia.skel.auth.JwtAuthInterceptor} fronts every route
 * declared on this controller and rejects unauthenticated /
 * malformed-token requests with a JSON 401 body.
 *
 * <p>Categories are shared (not per-user) but auth-protected — any
 * authenticated user can CRUD them. Items reference categories via an
 * optional {@code category_id} FK enforced at the entity level by
 * {@link app.marysia.skel.items.Item}'s {@code @ManyToOne}.
 */
@RestController
@RequestMapping("/api/categories")
public class CategoryController {

    private final CategoryService service;

    public CategoryController(CategoryService service) {
        this.service = service;
    }

    @GetMapping
    public List<Category> list(@SuppressWarnings("unused") AuthUser user) {
        return service.list();
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Category create(@SuppressWarnings("unused") AuthUser user,
                           @RequestBody NewCategoryRequest body) {
        return service.create(body);
    }

    @GetMapping("/{id}")
    public Category get(@SuppressWarnings("unused") AuthUser user, @PathVariable long id) {
        return service.get(id);
    }

    @PutMapping("/{id}")
    public Category update(@SuppressWarnings("unused") AuthUser user,
                           @PathVariable long id,
                           @RequestBody NewCategoryRequest body) {
        return service.update(id, body);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@SuppressWarnings("unused") AuthUser user, @PathVariable long id) {
        service.delete(id);
    }
}
