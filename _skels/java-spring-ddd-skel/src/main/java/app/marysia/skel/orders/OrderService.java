package app.marysia.skel.orders;

import app.marysia.skel.catalog.CatalogItem;
import app.marysia.skel.catalog.CatalogItemRepository;
import app.marysia.skel.orders.dto.ApproveRequest;
import app.marysia.skel.orders.dto.NewOrderLineRequest;
import app.marysia.skel.orders.dto.RejectRequest;
import app.marysia.skel.orders.dto.SetAddressRequest;
import app.marysia.skel.shared.NotFoundException;
import app.marysia.skel.shared.ValidationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Order-aggregate service.
 *
 * <p>Owns the {@code orders} / {@code order_lines} /
 * {@code order_addresses} repositories and coordinates the lifecycle
 * (draft &rarr; pending &rarr; approved/rejected). Cross-resource
 * lookup of the catalog row goes through {@link CatalogItemRepository}
 * — see the same pattern in the rust-actix DDD reference where
 * {@code orders::OrdersService} reads through
 * {@code catalog::CatalogService}.
 *
 * <p>Service methods throw {@link NotFoundException} /
 * {@link ValidationException} instead of leaking persistence-level
 * errors. The {@link app.marysia.skel.shared.GlobalExceptionHandler}
 * advice maps them to the canonical {@code {detail, status}} JSON body.
 */
@Service
public class OrderService {

    private final OrderRepository orders;
    private final OrderLineRepository orderLines;
    private final OrderAddressRepository orderAddresses;
    private final CatalogItemRepository catalog;

    public OrderService(OrderRepository orders,
                        OrderLineRepository orderLines,
                        OrderAddressRepository orderAddresses,
                        CatalogItemRepository catalog) {
        this.orders = orders;
        this.orderLines = orderLines;
        this.orderAddresses = orderAddresses;
        this.catalog = catalog;
    }

    public OrderRecord createDraft(long userId) {
        return orders.save(new OrderRecord(userId));
    }

    public List<OrderRecord> listForUser(long userId) {
        return orders.findAllByUserIdOrderByIdDesc(userId);
    }

    /**
     * Returns the order projection the React frontend expects: header
     * fields plus a flattened {@code lines} array (with the catalog
     * item's name) and an optional {@code address} block.
     */
    public Map<String, Object> getOrder(long id, long userId) {
        OrderRecord order = findOwnedOrder(id, userId);

        List<Map<String, Object>> lineDtos = new ArrayList<>();
        for (OrderLine line : orderLines.findAllByOrderIdOrderByIdAsc(id)) {
            CatalogItem ci = catalog.findById(line.getCatalogItemId()).orElse(null);
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("id", line.getId());
            m.put("catalog_item_id", line.getCatalogItemId());
            m.put("quantity", line.getQuantity());
            m.put("unit_price", line.getUnitPrice());
            m.put("item_name", ci == null ? null : ci.getName());
            lineDtos.add(m);
        }

        Map<String, Object> address = orderAddresses.findByOrderId(id)
            .map(a -> {
                Map<String, Object> m = new LinkedHashMap<>();
                m.put("id", a.getId());
                m.put("street", a.getStreet());
                m.put("city", a.getCity());
                m.put("zip_code", a.getZipCode());
                m.put("phone", a.getPhone());
                m.put("notes", a.getNotes());
                return m;
            })
            .orElse(null);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("id", order.getId());
        result.put("user_id", order.getUserId());
        result.put("status", order.getStatus());
        result.put("created_at", order.getCreatedAt());
        result.put("submitted_at", order.getSubmittedAt());
        result.put("wait_minutes", order.getWaitMinutes());
        result.put("feedback", order.getFeedback());
        result.put("lines", lineDtos);
        result.put("address", address);
        return result;
    }

    public Map<String, Object> addLine(long orderId, long userId, NewOrderLineRequest body) {
        OrderRecord order = findOwnedOrder(orderId, userId);
        if (!"draft".equals(order.getStatus())) {
            throw new ValidationException("can only add lines to draft orders");
        }
        if (body == null || body.catalogItemId() == null) {
            throw new ValidationException("catalog_item_id is required");
        }
        CatalogItem ci = catalog.findById(body.catalogItemId())
            .orElseThrow(() -> new NotFoundException(
                "catalog item " + body.catalogItemId() + " not found"));

        int qty = (body.quantity() != null && body.quantity() > 0) ? body.quantity() : 1;
        OrderLine line = orderLines.save(new OrderLine(orderId, ci.getId(), qty, ci.getPrice()));

        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("id", line.getId());
        resp.put("order_id", line.getOrderId());
        resp.put("catalog_item_id", line.getCatalogItemId());
        resp.put("quantity", line.getQuantity());
        resp.put("unit_price", line.getUnitPrice());
        return resp;
    }

    @Transactional
    public void deleteLine(long orderId, long userId, long lineId) {
        OrderRecord order = findOwnedOrder(orderId, userId);
        if (!"draft".equals(order.getStatus())) {
            throw new ValidationException("can only remove lines from draft orders");
        }
        long deleted = orderLines.deleteByIdAndOrderId(lineId, orderId);
        if (deleted == 0) {
            throw new NotFoundException("line " + lineId + " not found on order " + orderId);
        }
    }

    @Transactional
    public Map<String, Object> setAddress(long orderId, long userId, SetAddressRequest body) {
        OrderRecord order = findOwnedOrder(orderId, userId);
        if (!"draft".equals(order.getStatus())) {
            throw new ValidationException("can only set address on draft orders");
        }
        if (body == null
            || body.street() == null || body.street().isBlank()
            || body.city() == null || body.city().isBlank()
            || body.zipCode() == null || body.zipCode().isBlank()) {
            throw new ValidationException("street, city, and zip_code are required");
        }
        // Upsert: delete-then-insert keeps the @UniqueConstraint on
        // order_id satisfied without driver-specific UPSERT syntax.
        orderAddresses.deleteByOrderId(orderId);
        // Make sure the DELETE is flushed before the INSERT, otherwise
        // the unique constraint can fire when both statements reach
        // the JDBC connection inside the same transaction.
        orderAddresses.flush();
        OrderAddress addr = orderAddresses.save(new OrderAddress(
            orderId,
            body.street(),
            body.city(),
            body.zipCode(),
            body.phone() != null ? body.phone() : "",
            body.notes() != null ? body.notes() : ""
        ));

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("order_id", addr.getOrderId());
        result.put("street", addr.getStreet());
        result.put("city", addr.getCity());
        result.put("zip_code", addr.getZipCode());
        result.put("phone", addr.getPhone());
        result.put("notes", addr.getNotes());
        return result;
    }

    public OrderRecord submit(long orderId, long userId) {
        OrderRecord order = findOwnedOrder(orderId, userId);
        if (!"draft".equals(order.getStatus())) {
            throw new ValidationException("only draft orders can be submitted");
        }
        if (orderLines.countByOrderId(orderId) == 0) {
            throw new ValidationException("order must have at least one line to submit");
        }
        order.setStatus("pending");
        order.setSubmittedAt(LocalDateTime.now(ZoneOffset.UTC));
        return orders.save(order);
    }

    public OrderRecord approve(long orderId, long userId, ApproveRequest body) {
        OrderRecord order = findOwnedOrder(orderId, userId);
        if (!"pending".equals(order.getStatus())) {
            throw new ValidationException("only pending orders can be approved");
        }
        int wm = (body != null && body.waitMinutes() != null) ? body.waitMinutes() : 0;
        String fb = (body != null && body.feedback() != null) ? body.feedback() : "";
        order.setStatus("approved");
        order.setWaitMinutes(wm);
        order.setFeedback(fb);
        return orders.save(order);
    }

    public OrderRecord reject(long orderId, long userId, RejectRequest body) {
        OrderRecord order = findOwnedOrder(orderId, userId);
        if (!"pending".equals(order.getStatus())) {
            throw new ValidationException("only submitted orders can be rejected");
        }
        String feedback = (body != null && body.feedback() != null) ? body.feedback() : "";
        order.setStatus("rejected");
        order.setFeedback(feedback);
        return orders.save(order);
    }

    /**
     * Look up an order owned by {@code userId}; surfaces the
     * "not found / not yours" 404 the React frontend expects (we never
     * leak whether the id exists for another user — same as the
     * django-bolt parity).
     */
    private OrderRecord findOwnedOrder(long id, long userId) {
        OrderRecord order = orders.findById(id)
            .orElseThrow(() -> new NotFoundException("order " + id + " not found"));
        if (order.getUserId() != userId) {
            throw new NotFoundException("order " + id + " not found");
        }
        return order;
    }
}
