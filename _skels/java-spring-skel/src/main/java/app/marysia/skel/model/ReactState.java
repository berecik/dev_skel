package app.marysia.skel.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;

/**
 * Per-user JSON KV slice backing the React {@code useAppState<T>(key,
 * default)} hook.
 *
 * <p>The composite uniqueness on {@code (user_id, state_key)} matches
 * the django-bolt schema and is the reason callers can use the
 * {@code findByUserIdAndKey} derived query for the upsert path.
 */
@Entity
@Table(
    name = "react_state",
    uniqueConstraints = {
        @UniqueConstraint(name = "uk_react_state_user_key", columnNames = {"user_id", "state_key"})
    }
)
public class ReactState {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false)
    private long userId;

    /**
     * Mapped to the column {@code state_key} (not {@code key}) because
     * {@code key} is a reserved word in some SQL dialects (e.g.
     * Postgres). Java-side the field is named {@code key} for the
     * derived query method {@code findByUserIdAndKey}.
     */
    @Column(name = "state_key", nullable = false)
    private String key;

    @Column(name = "state_value", nullable = false, columnDefinition = "TEXT")
    private String value;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    public ReactState() {
    }

    public ReactState(long userId, String key, String value) {
        this.userId = userId;
        this.key = key;
        this.value = value;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public long getUserId() {
        return userId;
    }

    public void setUserId(long userId) {
        this.userId = userId;
    }

    public String getKey() {
        return key;
    }

    public void setKey(String key) {
        this.key = key;
    }

    public String getValue() {
        return value;
    }

    public void setValue(String value) {
        this.value = value;
    }

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(LocalDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }
}
