package com.example.skel.service;

import com.example.skel.model.Category;
import com.example.skel.repository.CategoryRepository;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Optional;

/**
 * Thin orchestration layer around {@link CategoryRepository}. Kept as a
 * separate bean so {@code CategoryController} stays I/O-only and the
 * business rules have a clear home.
 */
@Service
public class CategoryService {

    private final CategoryRepository categories;

    public CategoryService(CategoryRepository categories) {
        this.categories = categories;
    }

    public List<Category> findAll() {
        return categories.findAll();
    }

    public Optional<Category> findById(long id) {
        return categories.findById(id);
    }

    public Category create(String name, String description) {
        return categories.insert(name, description);
    }

    public Optional<Category> update(long id, String name, String description) {
        return categories.update(id, name, description);
    }

    public boolean delete(long id) {
        return categories.deleteById(id);
    }
}
