package app.marysia.skel.catalog;

import app.marysia.skel.auth.AuthUser;
import app.marysia.skel.catalog.dto.NewCatalogItemRequest;
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
 * Wrapper-shared {@code /api/catalog} endpoints. Reads are open to any
 * authenticated user; writes are open to any authenticated user too —
 * the catalog is shared across the wrapper. The
 * {@link app.marysia.skel.auth.JwtAuthInterceptor} fronts every route.
 */
@RestController
@RequestMapping("/api/catalog")
public class CatalogController {

    private final CatalogService service;

    public CatalogController(CatalogService service) {
        this.service = service;
    }

    @GetMapping
    public List<CatalogItem> list(@SuppressWarnings("unused") AuthUser user) {
        return service.list();
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public CatalogItem create(@SuppressWarnings("unused") AuthUser user,
                              @RequestBody NewCatalogItemRequest body) {
        return service.create(body);
    }

    @GetMapping("/{id}")
    public CatalogItem get(@SuppressWarnings("unused") AuthUser user, @PathVariable long id) {
        return service.get(id);
    }
}
