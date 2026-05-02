package app.marysia.skel.items;

import app.marysia.skel.categories.Category;
import app.marysia.skel.categories.CategoryRepository;
import app.marysia.skel.items.dto.NewItemRequest;
import app.marysia.skel.shared.NotFoundException;
import app.marysia.skel.shared.ValidationException;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * Service-layer logic for {@code /api/items}. Holds the
 * {@link ItemRepository} and (for FK lookup) the
 * {@link CategoryRepository}; the controller delegates every
 * persistence call to this class.
 *
 * <p>The cross-resource dependency on {@link CategoryRepository} is the
 * single legitimate inter-package coupling for items: an item's
 * {@code category_id} FK has to resolve against the categories module
 * before an item can be persisted. Mirrors the rust-actix DDD reference
 * where {@code ItemsService::create} re-uses
 * {@code categories::CategoriesService}.
 */
@Service
public class ItemService {

    private final ItemRepository items;
    private final CategoryRepository categories;

    public ItemService(ItemRepository items, CategoryRepository categories) {
        this.items = items;
        this.categories = categories;
    }

    public List<Item> list() {
        return items.findAllByOrderByCreatedAtDescIdDesc();
    }

    public Item get(long id) {
        return items.findById(id)
            .orElseThrow(() -> new NotFoundException("item " + id + " not found"));
    }

    public Item create(NewItemRequest body) {
        if (body == null || body.name() == null || body.name().isBlank()) {
            throw new ValidationException("item name cannot be empty");
        }
        boolean isCompleted = body.isCompleted() != null && body.isCompleted();
        Category category = null;
        if (body.categoryId() != null) {
            category = categories.findById(body.categoryId())
                .orElseThrow(() -> new ValidationException(
                    "category " + body.categoryId() + " not found"));
        }
        Item item = new Item(body.name(), body.description(), isCompleted, category);
        return items.save(item);
    }

    /**
     * Idempotent: completing an already-completed item is a no-op that
     * still returns the row (HTTP 200).
     */
    public Item complete(long id) {
        Item item = get(id);
        item.setCompleted(true);
        return items.save(item);
    }
}
