package app.marysia.skel.controller;

import app.marysia.skel.controller.ItemController.ApiException;
import app.marysia.skel.model.CatalogItem;
import app.marysia.skel.model.OrderAddress;
import app.marysia.skel.model.OrderLine;
import app.marysia.skel.model.OrderRecord;
import app.marysia.skel.repository.CatalogItemRepository;
import app.marysia.skel.repository.OrderAddressRepository;
import app.marysia.skel.repository.OrderLineRepository;
import app.marysia.skel.repository.OrderRepository;
import app.marysia.skel.security.AuthUser;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Order-workflow endpoints covering catalogue browsing, order creation,
 * line-item management, address capture, and order lifecycle (submit /
 * approve / reject).
 *
 * <p>All endpoints require a valid JWT via the
 * {@link app.marysia.skel.security.JwtAuthInterceptor}.
 */
@RestController
public class OrderController {

    private final CatalogItemRepository catalog;
    private final OrderRepository orders;
    private final OrderLineRepository orderLines;
    private final OrderAddressRepository orderAddresses;

    public OrderController(CatalogItemRepository catalog,
                           OrderRepository orders,
                           OrderLineRepository orderLines,
                           OrderAddressRepository orderAddresses) {
        this.catalog = catalog;
        this.orders = orders;
        this.orderLines = orderLines;
        this.orderAddresses = orderAddresses;
    }

    // ------------------------------------------------------------------
    // Catalog endpoints
    // ------------------------------------------------------------------

    @GetMapping("/api/catalog")
    public List<CatalogItem> listCatalog(@SuppressWarnings("unused") AuthUser user) {
        return catalog.findAllByOrderByIdAsc();
    }

    @PostMapping("/api/catalog")
    public ResponseEntity<CatalogItem> createCatalogItem(@SuppressWarnings("unused") AuthUser user,
                                                         @RequestBody CreateCatalogItemRequest body) {
        if (body == null || body.name() == null || body.name().isBlank()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "catalog item name cannot be empty");
        }
        if (body.price() == null || body.price() < 0) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "price must be non-negative");
        }
        CatalogItem ci = new CatalogItem(
            body.name(),
            body.description() != null ? body.description() : "",
            body.price(),
            body.category() != null ? body.category() : "",
            body.available() == null || body.available()
        );
        ci = catalog.save(ci);
        return ResponseEntity.status(HttpStatus.CREATED).body(ci);
    }

    @GetMapping("/api/catalog/{id}")
    public CatalogItem getCatalogItem(@SuppressWarnings("unused") AuthUser user,
                                      @PathVariable long id) {
        return catalog.findById(id)
            .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "catalog item " + id + " not found"));
    }

    // ------------------------------------------------------------------
    // Order CRUD
    // ------------------------------------------------------------------

    @PostMapping("/api/orders")
    public ResponseEntity<OrderRecord> createOrder(AuthUser user) {
        OrderRecord o = new OrderRecord(user.id());
        o = orders.save(o);
        return ResponseEntity.status(HttpStatus.CREATED).body(o);
    }

    @GetMapping("/api/orders")
    public List<OrderRecord> listOrders(AuthUser user) {
        return orders.findAllByUserIdOrderByIdDesc(user.id());
    }

    @GetMapping("/api/orders/{id}")
    public Map<String, Object> getOrder(AuthUser user, @PathVariable long id) {
        OrderRecord order = findOrderForUser(id, user.id());

        // Project lines + the catalog item's name into the response shape
        // the React frontend expects.
        List<Map<String, Object>> lineDtos = new java.util.ArrayList<>();
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

    // ------------------------------------------------------------------
    // Order lines
    // ------------------------------------------------------------------

    @PostMapping("/api/orders/{id}/lines")
    public ResponseEntity<Map<String, Object>> addLine(AuthUser user,
                                                       @PathVariable long id,
                                                       @RequestBody AddLineRequest body) {
        OrderRecord order = findOrderForUser(id, user.id());
        if (!"draft".equals(order.getStatus())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "can only add lines to draft orders");
        }
        if (body == null || body.catalogItemId() == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "catalog_item_id is required");
        }
        CatalogItem ci = catalog.findById(body.catalogItemId())
            .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND,
                "catalog item " + body.catalogItemId() + " not found"));

        int qty = (body.quantity() != null && body.quantity() > 0) ? body.quantity() : 1;
        OrderLine line = new OrderLine(id, ci.getId(), qty, ci.getPrice());
        line = orderLines.save(line);

        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("id", line.getId());
        resp.put("order_id", line.getOrderId());
        resp.put("catalog_item_id", line.getCatalogItemId());
        resp.put("quantity", line.getQuantity());
        resp.put("unit_price", line.getUnitPrice());
        return ResponseEntity.status(HttpStatus.CREATED).body(resp);
    }

    @DeleteMapping("/api/orders/{id}/lines/{lineId}")
    @Transactional
    public ResponseEntity<Void> deleteLine(AuthUser user,
                                           @PathVariable long id,
                                           @PathVariable long lineId) {
        OrderRecord order = findOrderForUser(id, user.id());
        if (!"draft".equals(order.getStatus())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "can only remove lines from draft orders");
        }
        long deleted = orderLines.deleteByIdAndOrderId(lineId, id);
        if (deleted == 0) {
            throw new ApiException(HttpStatus.NOT_FOUND, "line " + lineId + " not found on order " + id);
        }
        return ResponseEntity.noContent().build();
    }

    // ------------------------------------------------------------------
    // Address
    // ------------------------------------------------------------------

    @PutMapping("/api/orders/{id}/address")
    @Transactional
    public ResponseEntity<Map<String, Object>> setAddress(AuthUser user,
                                                          @PathVariable long id,
                                                          @RequestBody AddressRequest body) {
        OrderRecord order = findOrderForUser(id, user.id());
        if (!"draft".equals(order.getStatus())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "can only set address on draft orders");
        }
        if (body == null || body.street() == null || body.street().isBlank()
            || body.city() == null || body.city().isBlank()
            || body.zipCode() == null || body.zipCode().isBlank()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "street, city, and zip_code are required");
        }
        // Upsert: delete-then-insert keeps the @UniqueConstraint
        // on order_id satisfied without driver-specific UPSERT syntax.
        orderAddresses.deleteByOrderId(id);
        // Make sure the DELETE is flushed before the INSERT, otherwise
        // the unique constraint can fire when both statements reach
        // the JDBC connection inside the same transaction.
        orderAddresses.flush();
        OrderAddress addr = new OrderAddress(
            id,
            body.street(),
            body.city(),
            body.zipCode(),
            body.phone() != null ? body.phone() : "",
            body.notes() != null ? body.notes() : ""
        );
        addr = orderAddresses.save(addr);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("order_id", addr.getOrderId());
        result.put("street", addr.getStreet());
        result.put("city", addr.getCity());
        result.put("zip_code", addr.getZipCode());
        result.put("phone", addr.getPhone());
        result.put("notes", addr.getNotes());
        return ResponseEntity.ok(result);
    }

    // ------------------------------------------------------------------
    // Order lifecycle
    // ------------------------------------------------------------------

    @PostMapping("/api/orders/{id}/submit")
    public OrderRecord submitOrder(AuthUser user, @PathVariable long id) {
        OrderRecord order = findOrderForUser(id, user.id());
        if (!"draft".equals(order.getStatus())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "only draft orders can be submitted");
        }
        if (orderLines.countByOrderId(id) == 0) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "order must have at least one line to submit");
        }
        order.setStatus("pending");
        order.setSubmittedAt(LocalDateTime.now(ZoneOffset.UTC));
        return orders.save(order);
    }

    public record ApproveRequest(Integer wait_minutes, String feedback) {}

    @PostMapping("/api/orders/{id}/approve")
    public OrderRecord approveOrder(AuthUser user, @PathVariable long id,
                                    @RequestBody ApproveRequest body) {
        OrderRecord order = findOrderForUser(id, user.id());
        if (!"pending".equals(order.getStatus())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "only pending orders can be approved");
        }
        int wm = (body != null && body.wait_minutes() != null) ? body.wait_minutes() : 0;
        String fb = (body != null && body.feedback() != null) ? body.feedback() : "";
        order.setStatus("approved");
        order.setWaitMinutes(wm);
        order.setFeedback(fb);
        return orders.save(order);
    }

    @PostMapping("/api/orders/{id}/reject")
    public OrderRecord rejectOrder(AuthUser user,
                                   @PathVariable long id,
                                   @RequestBody(required = false) RejectRequest body) {
        OrderRecord order = findOrderForUser(id, user.id());
        if (!"pending".equals(order.getStatus())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "only submitted orders can be rejected");
        }
        String feedback = (body != null && body.feedback() != null) ? body.feedback() : "";
        order.setStatus("rejected");
        order.setFeedback(feedback);
        return orders.save(order);
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    private OrderRecord findOrderForUser(long id, long userId) {
        OrderRecord order = orders.findById(id)
            .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "order " + id + " not found"));
        if (order.getUserId() != userId) {
            throw new ApiException(HttpStatus.NOT_FOUND, "order " + id + " not found");
        }
        return order;
    }

    // ------------------------------------------------------------------
    // Exception handler (mirrors ItemController pattern)
    // ------------------------------------------------------------------

    @ExceptionHandler(ApiException.class)
    public ResponseEntity<Map<String, Object>> handleApiException(ApiException ex) {
        return ResponseEntity.status(ex.status()).body(Map.of(
            "detail", ex.getMessage(),
            "status", ex.status().value()
        ));
    }

    // ------------------------------------------------------------------
    // Request DTOs
    // ------------------------------------------------------------------

    public record CreateCatalogItemRequest(String name, String description, Double price,
                                           String category, Boolean available) {}

    public record AddLineRequest(Long catalogItemId, Integer quantity) {}

    public record AddressRequest(String street, String city, String zipCode,
                                 String phone, String notes) {}

    public record RejectRequest(String feedback) {}
}
