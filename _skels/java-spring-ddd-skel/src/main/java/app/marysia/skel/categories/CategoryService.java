package app.marysia.skel.categories;

import app.marysia.skel.categories.dto.NewCategoryRequest;
import app.marysia.skel.shared.NotFoundException;
import app.marysia.skel.shared.ValidationException;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * Service-layer logic for {@code /api/categories}. Holds the
 * {@link CategoryRepository} and enforces the validation invariants —
 * controllers stay thin and delegate every persistence operation to
 * this class.
 */
@Service
public class CategoryService {

    private final CategoryRepository categories;

    public CategoryService(CategoryRepository categories) {
        this.categories = categories;
    }

    public List<Category> list() {
        return categories.findAllByOrderByIdAsc();
    }

    public Category get(long id) {
        return categories.findById(id)
            .orElseThrow(() -> new NotFoundException("category " + id + " not found"));
    }

    public Category create(NewCategoryRequest body) {
        validate(body);
        return categories.save(new Category(body.name(), body.description()));
    }

    public Category update(long id, NewCategoryRequest body) {
        validate(body);
        Category c = get(id);
        c.setName(body.name());
        c.setDescription(body.description());
        return categories.save(c);
    }

    /**
     * Delete a category by id. Items that referenced it via
     * {@code @OnDelete(SET_NULL)} have their FK silently nulled out —
     * the cascade is enforced at the database layer by Hibernate.
     */
    public void delete(long id) {
        if (!categories.existsById(id)) {
            throw new NotFoundException("category " + id + " not found");
        }
        categories.deleteById(id);
    }

    private static void validate(NewCategoryRequest body) {
        if (body == null || body.name() == null || body.name().isBlank()) {
            throw new ValidationException("category name cannot be empty");
        }
    }
}
