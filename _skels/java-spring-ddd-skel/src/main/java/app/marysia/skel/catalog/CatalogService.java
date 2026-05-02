package app.marysia.skel.catalog;

import app.marysia.skel.catalog.dto.NewCatalogItemRequest;
import app.marysia.skel.shared.NotFoundException;
import app.marysia.skel.shared.ValidationException;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * Service-layer logic for {@code /api/catalog}. Currently a thin
 * facade around {@link CatalogItemRepository} — the catalog has no
 * order-side dependency: orders link back via the scalar
 * {@code catalog_item_id} FK.
 */
@Service
public class CatalogService {

    private final CatalogItemRepository catalog;

    public CatalogService(CatalogItemRepository catalog) {
        this.catalog = catalog;
    }

    public List<CatalogItem> list() {
        return catalog.findAllByOrderByIdAsc();
    }

    public CatalogItem get(long id) {
        return catalog.findById(id)
            .orElseThrow(() -> new NotFoundException("catalog item " + id + " not found"));
    }

    public CatalogItem create(NewCatalogItemRequest body) {
        if (body == null || body.name() == null || body.name().isBlank()) {
            throw new ValidationException("catalog item name cannot be empty");
        }
        if (body.price() == null || body.price() < 0) {
            throw new ValidationException("price must be non-negative");
        }
        CatalogItem ci = new CatalogItem(
            body.name(),
            body.description() != null ? body.description() : "",
            body.price(),
            body.category() != null ? body.category() : "",
            body.available() == null || body.available()
        );
        return catalog.save(ci);
    }
}
