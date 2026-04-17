package com.example.skel.service;

import com.example.skel.model.Item;
import com.example.skel.repository.ItemRepository;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Optional;

/**
 * Thin orchestration layer around {@link ItemRepository}. Kept as a
 * separate bean so {@code ItemController} stays I/O-only and the
 * business rules (e.g. ownership checks, future event publishing) have
 * a clear home.
 */
@Service
public class ItemService {

    private final ItemRepository items;

    public ItemService(ItemRepository items) {
        this.items = items;
    }

    public List<Item> findAll() {
        return items.findAll();
    }

    public Optional<Item> findById(long id) {
        return items.findById(id);
    }

    public Item create(String name, String description, boolean isCompleted, Long categoryId) {
        return items.insert(name, description, isCompleted, categoryId);
    }

    public Optional<Item> complete(long id) {
        return items.markCompleted(id);
    }
}
