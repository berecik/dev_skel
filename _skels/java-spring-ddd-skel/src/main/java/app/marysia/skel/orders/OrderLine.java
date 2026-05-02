package app.marysia.skel.orders;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import org.hibernate.annotations.OnDelete;
import org.hibernate.annotations.OnDeleteAction;

/**
 * Line item belonging to an {@link OrderRecord}.
 *
 * <p>The {@code order_id} FK has {@code @OnDelete(CASCADE)} so deleting
 * an order takes its lines with it; the {@code catalog_item_id} FK is
 * a hard reference (deleting a catalog item with referencing lines
 * raises an FK violation by design — historical orders should keep
 * pointing at the row that was charged).
 *
 * <p>The reference to the parent order is lazy + JSON-ignored so the
 * line serialises with scalar IDs only — the
 * {@link OrderService#getOrder(long, long)} projection adds a
 * {@code item_name} field by re-reading the catalog row.
 */
@Entity
@Table(name = "order_lines")
public class OrderLine {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "order_id", nullable = false)
    private long orderId;

    @Column(name = "catalog_item_id", nullable = false)
    private long catalogItemId;

    @Column(nullable = false)
    private int quantity = 1;

    @Column(name = "unit_price", nullable = false)
    private double unitPrice;

    /**
     * Read-only navigation to the parent order — Hibernate uses this to
     * issue the {@code @OnDelete(CASCADE)} FK. The {@code insertable=false /
     * updatable=false} pair tells JPA the {@code order_id} scalar above
     * is the source of truth for writes.
     */
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "order_id", insertable = false, updatable = false)
    @OnDelete(action = OnDeleteAction.CASCADE)
    @com.fasterxml.jackson.annotation.JsonIgnore
    private OrderRecord order;

    public OrderLine() {
    }

    public OrderLine(long orderId, long catalogItemId, int quantity, double unitPrice) {
        this.orderId = orderId;
        this.catalogItemId = catalogItemId;
        this.quantity = quantity;
        this.unitPrice = unitPrice;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public long getOrderId() {
        return orderId;
    }

    public void setOrderId(long orderId) {
        this.orderId = orderId;
    }

    public long getCatalogItemId() {
        return catalogItemId;
    }

    public void setCatalogItemId(long catalogItemId) {
        this.catalogItemId = catalogItemId;
    }

    public int getQuantity() {
        return quantity;
    }

    public void setQuantity(int quantity) {
        this.quantity = quantity;
    }

    public double getUnitPrice() {
        return unitPrice;
    }

    public void setUnitPrice(double unitPrice) {
        this.unitPrice = unitPrice;
    }
}
