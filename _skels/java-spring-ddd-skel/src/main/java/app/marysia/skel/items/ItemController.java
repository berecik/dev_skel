package app.marysia.skel.items;

import app.marysia.skel.auth.AuthUser;
import app.marysia.skel.items.dto.NewItemRequest;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * Wrapper-shared {@code /api/items} CRUD that the React frontend
 * consumes. Every endpoint requires a Bearer JWT — the
 * {@link app.marysia.skel.auth.JwtAuthInterceptor} fronts every route
 * declared on this controller and rejects unauthenticated /
 * malformed-token requests with a JSON 401 body.
 *
 * <p>{@link AuthUser} is injected by
 * {@link app.marysia.skel.auth.AuthUserArgumentResolver}; we accept it
 * on every method so future tightening (e.g. ownership scoping) does
 * not need to add a new parameter to each controller. Today the auth
 * principal is unused at the route level — every authenticated user
 * sees every item, matching the django-bolt parity contract.
 */
@RestController
@RequestMapping("/api/items")
public class ItemController {

    private final ItemService service;

    public ItemController(ItemService service) {
        this.service = service;
    }

    @GetMapping
    public List<Item> list(@SuppressWarnings("unused") AuthUser user) {
        return service.list();
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Item create(@SuppressWarnings("unused") AuthUser user,
                       @RequestBody NewItemRequest body) {
        return service.create(body);
    }

    @GetMapping("/{id}")
    public Item get(@SuppressWarnings("unused") AuthUser user, @PathVariable long id) {
        return service.get(id);
    }

    /**
     * {@code POST /api/items/{id}/complete} — flips
     * {@code is_completed=true} and returns the refreshed row.
     * Idempotent: completing an already-completed item is a no-op
     * that still returns 200.
     */
    @PostMapping("/{id}/complete")
    public Item complete(@SuppressWarnings("unused") AuthUser user, @PathVariable long id) {
        return service.complete(id);
    }
}
