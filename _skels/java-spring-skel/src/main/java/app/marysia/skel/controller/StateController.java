package app.marysia.skel.controller;

import app.marysia.skel.model.ReactState;
import app.marysia.skel.repository.ReactStateRepository;
import app.marysia.skel.security.AuthUser;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Wrapper-shared {@code /api/state} per-user JSON KV store backing the
 * React {@code useAppState<T>(key, default)} hook.
 *
 * <p>Wire format (from {@code ts-react-skel/src/state/state-api.ts}):
 * <ul>
 *   <li>{@code GET /api/state} → {@code { "<key>": "<json string>" }}
 *       for the authenticated user.</li>
 *   <li>{@code PUT /api/state/{key}} body
 *       {@code { "value": "<json string>" }} — upsert the slice.</li>
 *   <li>{@code DELETE /api/state/{key}} → drop the slice.</li>
 * </ul>
 *
 * <p>Every endpoint requires a Bearer JWT via the
 * {@link app.marysia.skel.security.JwtAuthInterceptor}.
 */
@RestController
@RequestMapping("/api/state")
public class StateController {

    private final ReactStateRepository states;

    public StateController(ReactStateRepository states) {
        this.states = states;
    }

    @GetMapping
    public Map<String, String> list(AuthUser user) {
        Map<String, String> out = new LinkedHashMap<>();
        for (ReactState s : states.findAllByUserIdOrderByKeyAsc(user.id())) {
            out.put(s.getKey(), s.getValue());
        }
        return out;
    }

    @PutMapping("/{key}")
    public Map<String, Object> upsert(AuthUser user,
                                      @PathVariable String key,
                                      @RequestBody UpsertRequest body) {
        String value = body == null || body.value() == null ? "" : body.value();
        ReactState row = states.findByUserIdAndKey(user.id(), key)
            .orElseGet(() -> new ReactState(user.id(), key, value));
        row.setValue(value);
        states.save(row);
        return Map.of("key", key);
    }

    @DeleteMapping("/{key}")
    @Transactional
    public Map<String, Object> delete(AuthUser user, @PathVariable String key) {
        states.deleteByUserIdAndKey(user.id(), key);
        return Map.of();
    }

    public record UpsertRequest(String value) {
    }
}
