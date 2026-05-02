package app.marysia.skel.items;

import app.marysia.skel.categories.Category;
import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.OnDelete;
import org.hibernate.annotations.OnDeleteAction;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;

/**
 * Wrapper-shared {@code items} resource consumed by the React frontend
 * via {@code ${BACKEND_URL}/api/items}.
 *
 * <p>Field layout mirrors the django-bolt skeleton's {@code Item} model
 * so a single {@code _shared/db.sqlite3} is interchangeable across the
 * Python and JVM backends.
 *
 * <p>{@code category} uses a lazy {@link ManyToOne} association with
 * {@code @OnDelete(SET_NULL)} so deleting a category sets the FK to
 * {@code NULL} on every item that referenced it (matching the
 * django-bolt {@code on_delete=SET_NULL} contract). The associated
 * category lives in the {@code app.marysia.skel.categories} module —
 * the cross-package association is the only place an entity in this
 * skeleton refers across resource boundaries; the FK is owned by the
 * {@code items} side because the items module is the consumer.
 *
 * <p>Jackson serialises the camelCase Java fields to snake_case JSON
 * keys ({@code is_completed}, {@code category_id}, {@code created_at},
 * {@code updated_at}) because
 * {@code spring.jackson.property-naming-strategy=SNAKE_CASE} is set
 * globally in {@code application.properties}.
 */
@Entity
@Table(name = "items")
public class Item {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String name;

    @Column(columnDefinition = "TEXT")
    private String description;

    @Column(name = "is_completed", nullable = false)
    private boolean isCompleted;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "category_id")
    @OnDelete(action = OnDeleteAction.SET_NULL)
    @JsonIgnore
    private Category category;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    public Item() {
    }

    public Item(String name, String description, boolean isCompleted, Category category) {
        this.name = name;
        this.description = description;
        this.isCompleted = isCompleted;
        this.category = category;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    @com.fasterxml.jackson.annotation.JsonProperty("is_completed")
    public boolean isCompleted() {
        return isCompleted;
    }

    @com.fasterxml.jackson.annotation.JsonProperty("is_completed")
    public void setCompleted(boolean completed) {
        isCompleted = completed;
    }

    public Category getCategory() {
        return category;
    }

    public void setCategory(Category category) {
        this.category = category;
    }

    /**
     * Convenience for the wire format — the React frontend's TypeScript
     * type expects {@code category_id} (a scalar long), not a nested
     * category object. Returning {@code null} when the FK is unset
     * matches the django-bolt response shape.
     */
    public Long getCategoryId() {
        return category == null ? null : category.getId();
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(LocalDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }
}
