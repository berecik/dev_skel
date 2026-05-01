package app.marysia.skel.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;

/**
 * Wrapper-shared {@code orders} resource representing a customer order.
 * Named {@code OrderRecord} to avoid clashing with {@link java.util.Order}
 * (preview API in recent JDKs) and SQL reserved words.
 *
 * <p>The user FK is stored as a scalar {@code userId} (not a JPA
 * {@link jakarta.persistence.ManyToOne} association) so the controller's
 * ownership check stays a single column comparison without forcing a
 * join. Cascade behaviour for child rows ({@link OrderLine},
 * {@link OrderAddress}) is handled at the FK level by the children's
 * {@code @OnDelete(CASCADE)} annotations.
 *
 * <p>Jackson serialises the camelCase Java fields to snake_case JSON
 * keys because
 * {@code spring.jackson.property-naming-strategy=SNAKE_CASE} is set
 * globally in {@code application.properties}.
 */
@Entity
@Table(name = "orders")
public class OrderRecord {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false)
    private long userId;

    @Column(nullable = false)
    private String status = "draft";

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "submitted_at")
    private LocalDateTime submittedAt;

    @Column(name = "wait_minutes")
    private Integer waitMinutes;

    @Column(columnDefinition = "TEXT")
    private String feedback;

    public OrderRecord() {
    }

    public OrderRecord(long userId) {
        this.userId = userId;
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

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }

    public LocalDateTime getSubmittedAt() {
        return submittedAt;
    }

    public void setSubmittedAt(LocalDateTime submittedAt) {
        this.submittedAt = submittedAt;
    }

    public Integer getWaitMinutes() {
        return waitMinutes;
    }

    public void setWaitMinutes(Integer waitMinutes) {
        this.waitMinutes = waitMinutes;
    }

    public String getFeedback() {
        return feedback;
    }

    public void setFeedback(String feedback) {
        this.feedback = feedback;
    }
}
