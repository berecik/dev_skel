package com.example.skel.controller;

import com.example.skel.controller.ItemController.ApiException;
import com.example.skel.model.CatalogItem;
import com.example.skel.model.OrderRecord;
import com.example.skel.security.AuthUser;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.web.bind.annotation.*;

import java.sql.PreparedStatement;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * Order-workflow endpoints covering catalogue browsing, order creation,
 * line-item management, address capture, and order lifecycle (submit /
 * approve / reject).
 *
 * <p>All endpoints require a valid JWT via the
 * {@link com.example.skel.security.JwtAuthInterceptor}.
 */
@RestController
public class OrderController {

    private final JdbcTemplate jdbc;
    private final JdbcClient client;

    public OrderController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
        this.client = JdbcClient.create(jdbc);
    }

    // ------------------------------------------------------------------
    // Row mappers
    // ------------------------------------------------------------------

    private static final RowMapper<CatalogItem> CATALOG_MAPPER = (rs, _row) -> new CatalogItem(
        rs.getLong("id"),
        rs.getString("name"),
        rs.getString("description"),
        rs.getDouble("price"),
        rs.getString("category"),
        rs.getBoolean("available")
    );

    private static final RowMapper<OrderRecord> ORDER_MAPPER = (rs, _row) -> new OrderRecord(
        rs.getLong("id"),
        rs.getLong("user_id"),
        rs.getString("status"),
        rs.getString("created_at"),
        rs.getString("submitted_at"),
        rs.getObject("wait_minutes") != null ? rs.getInt("wait_minutes") : null,
        rs.getString("feedback")
    );

    // ------------------------------------------------------------------
    // Catalog endpoints
    // ------------------------------------------------------------------

    @GetMapping("/api/catalog")
    public List<CatalogItem> listCatalog(@SuppressWarnings("unused") AuthUser user) {
        return client
            .sql("SELECT id, name, description, price, category, available FROM catalog_items ORDER BY id")
            .query(CATALOG_MAPPER)
            .list();
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
        var keyHolder = new org.springframework.jdbc.support.GeneratedKeyHolder();
        jdbc.update(connection -> {
            PreparedStatement ps = connection.prepareStatement(
                "INSERT INTO catalog_items (name, description, price, category, available) VALUES (?, ?, ?, ?, ?)",
                new String[]{"id"}
            );
            ps.setString(1, body.name());
            ps.setString(2, body.description() != null ? body.description() : "");
            ps.setDouble(3, body.price());
            ps.setString(4, body.category() != null ? body.category() : "");
            ps.setBoolean(5, body.available() == null || body.available());
            return ps;
        }, keyHolder);
        long newId = Objects.requireNonNull(keyHolder.getKey()).longValue();
        CatalogItem created = new CatalogItem(newId, body.name(),
            body.description() != null ? body.description() : "",
            body.price(),
            body.category() != null ? body.category() : "",
            body.available() == null || body.available());
        return ResponseEntity.status(HttpStatus.CREATED).body(created);
    }

    @GetMapping("/api/catalog/{id}")
    public CatalogItem getCatalogItem(@SuppressWarnings("unused") AuthUser user,
                                      @PathVariable long id) {
        try {
            return client
                .sql("SELECT id, name, description, price, category, available FROM catalog_items WHERE id = ?")
                .param(id)
                .query(CATALOG_MAPPER)
                .single();
        } catch (EmptyResultDataAccessException e) {
            throw new ApiException(HttpStatus.NOT_FOUND, "catalog item " + id + " not found");
        }
    }

    // ------------------------------------------------------------------
    // Order CRUD
    // ------------------------------------------------------------------

    @PostMapping("/api/orders")
    public ResponseEntity<OrderRecord> createOrder(AuthUser user) {
        var keyHolder = new org.springframework.jdbc.support.GeneratedKeyHolder();
        jdbc.update(connection -> {
            PreparedStatement ps = connection.prepareStatement(
                "INSERT INTO orders (user_id) VALUES (?)",
                new String[]{"id"}
            );
            ps.setLong(1, user.id());
            return ps;
        }, keyHolder);
        long newId = Objects.requireNonNull(keyHolder.getKey()).longValue();
        OrderRecord created = findOrderById(newId);
        return ResponseEntity.status(HttpStatus.CREATED).body(created);
    }

    @GetMapping("/api/orders")
    public List<OrderRecord> listOrders(AuthUser user) {
        return client
            .sql("SELECT id, user_id, status, created_at, submitted_at, wait_minutes, feedback "
                + "FROM orders WHERE user_id = ? ORDER BY id DESC")
            .param(user.id())
            .query(ORDER_MAPPER)
            .list();
    }

    @GetMapping("/api/orders/{id}")
    public Map<String, Object> getOrder(AuthUser user, @PathVariable long id) {
        OrderRecord order = findOrderByIdForUser(id, user.id());
        List<Map<String, Object>> lines = client
            .sql("SELECT ol.id, ol.catalog_item_id, ol.quantity, ol.unit_price, ci.name AS item_name "
                + "FROM order_lines ol JOIN catalog_items ci ON ol.catalog_item_id = ci.id "
                + "WHERE ol.order_id = ? ORDER BY ol.id")
            .param(id)
            .query((rs, _row) -> {
                Map<String, Object> m = new LinkedHashMap<>();
                m.put("id", rs.getLong("id"));
                m.put("catalog_item_id", rs.getLong("catalog_item_id"));
                m.put("quantity", rs.getInt("quantity"));
                m.put("unit_price", rs.getDouble("unit_price"));
                m.put("item_name", rs.getString("item_name"));
                return m;
            })
            .list();
        Map<String, Object> address = null;
        try {
            var addrRow = client
                .sql("SELECT id, street, city, zip_code, phone, notes FROM order_addresses WHERE order_id = ?")
                .param(id)
                .query((rs, _row) -> {
                    Map<String, Object> m = new LinkedHashMap<>();
                    m.put("id", rs.getLong("id"));
                    m.put("street", rs.getString("street"));
                    m.put("city", rs.getString("city"));
                    m.put("zip_code", rs.getString("zip_code"));
                    m.put("phone", rs.getString("phone"));
                    m.put("notes", rs.getString("notes"));
                    return m;
                })
                .single();
            address = addrRow;
        } catch (EmptyResultDataAccessException ignored) {
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("id", order.id());
        result.put("user_id", order.userId());
        result.put("status", order.status());
        result.put("created_at", order.createdAt());
        result.put("submitted_at", order.submittedAt());
        result.put("wait_minutes", order.waitMinutes());
        result.put("feedback", order.feedback());
        result.put("lines", lines);
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
        OrderRecord order = findOrderByIdForUser(id, user.id());
        if (!"draft".equals(order.status())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "can only add lines to draft orders");
        }
        if (body == null || body.catalogItemId() == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "catalog_item_id is required");
        }
        // Verify catalog item exists and get its price
        CatalogItem catalogItem;
        try {
            catalogItem = client
                .sql("SELECT id, name, description, price, category, available FROM catalog_items WHERE id = ?")
                .param(body.catalogItemId())
                .query(CATALOG_MAPPER)
                .single();
        } catch (EmptyResultDataAccessException e) {
            throw new ApiException(HttpStatus.NOT_FOUND, "catalog item " + body.catalogItemId() + " not found");
        }

        int qty = (body.quantity() != null && body.quantity() > 0) ? body.quantity() : 1;
        double unitPrice = catalogItem.price();

        var keyHolder = new org.springframework.jdbc.support.GeneratedKeyHolder();
        jdbc.update(connection -> {
            PreparedStatement ps = connection.prepareStatement(
                "INSERT INTO order_lines (order_id, catalog_item_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                new String[]{"id"}
            );
            ps.setLong(1, id);
            ps.setLong(2, body.catalogItemId());
            ps.setInt(3, qty);
            ps.setDouble(4, unitPrice);
            return ps;
        }, keyHolder);
        long lineId = Objects.requireNonNull(keyHolder.getKey()).longValue();

        Map<String, Object> line = new LinkedHashMap<>();
        line.put("id", lineId);
        line.put("order_id", id);
        line.put("catalog_item_id", body.catalogItemId());
        line.put("quantity", qty);
        line.put("unit_price", unitPrice);
        return ResponseEntity.status(HttpStatus.CREATED).body(line);
    }

    @DeleteMapping("/api/orders/{id}/lines/{lineId}")
    public ResponseEntity<Void> deleteLine(AuthUser user,
                                           @PathVariable long id,
                                           @PathVariable long lineId) {
        OrderRecord order = findOrderByIdForUser(id, user.id());
        if (!"draft".equals(order.status())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "can only remove lines from draft orders");
        }
        int deleted = jdbc.update("DELETE FROM order_lines WHERE id = ? AND order_id = ?", lineId, id);
        if (deleted == 0) {
            throw new ApiException(HttpStatus.NOT_FOUND, "line " + lineId + " not found on order " + id);
        }
        return ResponseEntity.noContent().build();
    }

    // ------------------------------------------------------------------
    // Address
    // ------------------------------------------------------------------

    @PutMapping("/api/orders/{id}/address")
    public ResponseEntity<Map<String, Object>> setAddress(AuthUser user,
                                                          @PathVariable long id,
                                                          @RequestBody AddressRequest body) {
        OrderRecord order = findOrderByIdForUser(id, user.id());
        if (!"draft".equals(order.status())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "can only set address on draft orders");
        }
        if (body == null || body.street() == null || body.street().isBlank()
            || body.city() == null || body.city().isBlank()
            || body.zipCode() == null || body.zipCode().isBlank()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "street, city, and zip_code are required");
        }
        // Upsert: delete existing then insert
        jdbc.update("DELETE FROM order_addresses WHERE order_id = ?", id);
        jdbc.update("INSERT INTO order_addresses (order_id, street, city, zip_code, phone, notes) VALUES (?, ?, ?, ?, ?, ?)",
            id, body.street(), body.city(), body.zipCode(),
            body.phone() != null ? body.phone() : "",
            body.notes() != null ? body.notes() : "");

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("order_id", id);
        result.put("street", body.street());
        result.put("city", body.city());
        result.put("zip_code", body.zipCode());
        result.put("phone", body.phone() != null ? body.phone() : "");
        result.put("notes", body.notes() != null ? body.notes() : "");
        return ResponseEntity.ok(result);
    }

    // ------------------------------------------------------------------
    // Order lifecycle
    // ------------------------------------------------------------------

    @PostMapping("/api/orders/{id}/submit")
    public OrderRecord submitOrder(AuthUser user, @PathVariable long id) {
        OrderRecord order = findOrderByIdForUser(id, user.id());
        if (!"draft".equals(order.status())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "only draft orders can be submitted");
        }
        // Must have at least one line
        Integer lineCount = jdbc.queryForObject(
            "SELECT COUNT(*) FROM order_lines WHERE order_id = ?", Integer.class, id);
        if (lineCount == null || lineCount == 0) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "order must have at least one line to submit");
        }
        jdbc.update("UPDATE orders SET status = 'pending', submitted_at = CURRENT_TIMESTAMP WHERE id = ?", id);
        return findOrderById(id);
    }

    public record ApproveRequest(Integer wait_minutes, String feedback) {}

    @PostMapping("/api/orders/{id}/approve")
    public OrderRecord approveOrder(AuthUser user, @PathVariable long id,
                                    @RequestBody ApproveRequest body) {
        OrderRecord order = findOrderByIdForUser(id, user.id());
        if (!"pending".equals(order.status())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "only pending orders can be approved");
        }
        int wm = (body != null && body.wait_minutes() != null) ? body.wait_minutes() : 0;
        String fb = (body != null && body.feedback() != null) ? body.feedback() : "";
        jdbc.update("UPDATE orders SET status = 'approved', wait_minutes = ?, feedback = ? WHERE id = ?", wm, fb, id);
        return findOrderById(id);
    }

    @PostMapping("/api/orders/{id}/reject")
    public OrderRecord rejectOrder(AuthUser user,
                                   @PathVariable long id,
                                   @RequestBody(required = false) RejectRequest body) {
        OrderRecord order = findOrderByIdForUser(id, user.id());
        if (!"pending".equals(order.status())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "only submitted orders can be rejected");
        }
        String feedback = (body != null && body.feedback() != null) ? body.feedback() : "";
        jdbc.update("UPDATE orders SET status = 'rejected', feedback = ? WHERE id = ?", feedback, id);
        return findOrderById(id);
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    private OrderRecord findOrderById(long id) {
        try {
            return client
                .sql("SELECT id, user_id, status, created_at, submitted_at, wait_minutes, feedback "
                    + "FROM orders WHERE id = ?")
                .param(id)
                .query(ORDER_MAPPER)
                .single();
        } catch (EmptyResultDataAccessException e) {
            throw new ApiException(HttpStatus.NOT_FOUND, "order " + id + " not found");
        }
    }

    private OrderRecord findOrderByIdForUser(long id, long userId) {
        OrderRecord order = findOrderById(id);
        if (order.userId() != userId) {
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
