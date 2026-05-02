package app.marysia.skel.state;

import app.marysia.skel.auth.AuthUser;
import app.marysia.skel.state.dto.StateUpsertRequest;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * Wrapper-shared {@code /api/state} per-user JSON KV store backing the
 * React {@code useAppState<T>(key, default)} hook.
 *
 * <p>Wire format (from {@code ts-react-skel/src/state/state-api.ts}):
 * <ul>
 *   <li>{@code GET /api/state} &rarr; {@code { "<key>": "<json string>" }}
 *       for the authenticated user.</li>
 *   <li>{@code PUT /api/state/{key}} body
 *       {@code { "value": "<json string>" }} — upsert the slice.</li>
 *   <li>{@code DELETE /api/state/{key}} &rarr; drop the slice.</li>
 * </ul>
 *
 * <p>Every endpoint requires a Bearer JWT via the
 * {@link app.marysia.skel.auth.JwtAuthInterceptor}.
 */
@RestController
@RequestMapping("/api/state")
public class StateController {

    private final StateService service;

    public StateController(StateService service) {
        this.service = service;
    }

    @GetMapping
    public Map<String, String> list(AuthUser user) {
        return service.list(user.id());
    }

    @PutMapping("/{key}")
    public Map<String, Object> upsert(AuthUser user,
                                      @PathVariable String key,
                                      @RequestBody StateUpsertRequest body) {
        String value = body == null ? null : body.value();
        service.upsert(user.id(), key, value);
        return Map.of("key", key);
    }

    @DeleteMapping("/{key}")
    public Map<String, Object> delete(AuthUser user, @PathVariable String key) {
        service.delete(user.id(), key);
        return Map.of();
    }
}
