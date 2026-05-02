package app.marysia.skel.orders;

import app.marysia.skel.auth.AuthUser;
import app.marysia.skel.orders.dto.ApproveRequest;
import app.marysia.skel.orders.dto.NewOrderLineRequest;
import app.marysia.skel.orders.dto.RejectRequest;
import app.marysia.skel.orders.dto.SetAddressRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * Order-workflow endpoints. All routes require a valid JWT — the
 * {@link app.marysia.skel.auth.JwtAuthInterceptor} fronts the
 * {@code /api/orders/**} URL pattern.
 *
 * <p>The controller is thin: it extracts the principal via
 * {@link AuthUser}, delegates to {@link OrderService}, and returns a
 * {@link ResponseEntity} with the matching status. Validation, lookup
 * misses, and lifecycle invariants live in the service and surface
 * via {@link app.marysia.skel.shared.DomainException} subclasses.
 */
@RestController
@RequestMapping("/api/orders")
public class OrderController {

    private final OrderService service;

    public OrderController(OrderService service) {
        this.service = service;
    }

    @PostMapping
    public ResponseEntity<OrderRecord> createOrder(AuthUser user) {
        OrderRecord o = service.createDraft(user.id());
        return ResponseEntity.status(HttpStatus.CREATED).body(o);
    }

    @GetMapping
    public List<OrderRecord> listOrders(AuthUser user) {
        return service.listForUser(user.id());
    }

    @GetMapping("/{id}")
    public Map<String, Object> getOrder(AuthUser user, @PathVariable long id) {
        return service.getOrder(id, user.id());
    }

    @PostMapping("/{id}/lines")
    public ResponseEntity<Map<String, Object>> addLine(AuthUser user,
                                                       @PathVariable long id,
                                                       @RequestBody NewOrderLineRequest body) {
        Map<String, Object> resp = service.addLine(id, user.id(), body);
        return ResponseEntity.status(HttpStatus.CREATED).body(resp);
    }

    @DeleteMapping("/{id}/lines/{lineId}")
    public ResponseEntity<Void> deleteLine(AuthUser user,
                                           @PathVariable long id,
                                           @PathVariable long lineId) {
        service.deleteLine(id, user.id(), lineId);
        return ResponseEntity.noContent().build();
    }

    @PutMapping("/{id}/address")
    public ResponseEntity<Map<String, Object>> setAddress(AuthUser user,
                                                          @PathVariable long id,
                                                          @RequestBody SetAddressRequest body) {
        return ResponseEntity.ok(service.setAddress(id, user.id(), body));
    }

    @PostMapping("/{id}/submit")
    public OrderRecord submitOrder(AuthUser user, @PathVariable long id) {
        return service.submit(id, user.id());
    }

    @PostMapping("/{id}/approve")
    public OrderRecord approveOrder(AuthUser user, @PathVariable long id,
                                    @RequestBody ApproveRequest body) {
        return service.approve(id, user.id(), body);
    }

    @PostMapping("/{id}/reject")
    public OrderRecord rejectOrder(AuthUser user,
                                   @PathVariable long id,
                                   @RequestBody(required = false) RejectRequest body) {
        return service.reject(id, user.id(), body);
    }
}
