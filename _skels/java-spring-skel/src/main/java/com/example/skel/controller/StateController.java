package com.example.skel.controller;

import com.example.skel.security.AuthUser;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.simple.JdbcClient;
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
 * {@link com.example.skel.security.JwtAuthInterceptor}.
 */
@RestController
@RequestMapping("/api/state")
public class StateController {

    private final JdbcClient client;

    public StateController(JdbcTemplate jdbc) {
        this.client = JdbcClient.create(jdbc);
    }

    @GetMapping
    public Map<String, String> list(AuthUser user) {
        Map<String, String> out = new LinkedHashMap<>();
        client
            .sql("SELECT state_key, state_value FROM react_state WHERE user_id = ? ORDER BY state_key")
            .param(user.id())
            .query((rs, _row) -> {
                out.put(rs.getString("state_key"), rs.getString("state_value"));
                return null;
            })
            .list();
        return out;
    }

    @PutMapping("/{key}")
    public Map<String, Object> upsert(AuthUser user,
                                      @PathVariable String key,
                                      @RequestBody UpsertRequest body) {
        String value = body == null || body.value() == null ? "" : body.value();
        // Try INSERT first; if the (user_id, state_key) UNIQUE
        // constraint fires, fall through to UPDATE. We avoid
        // dialect-specific upsert syntax (`ON CONFLICT` in SQLite/PG
        // vs. `MERGE` in H2) by branching on the row count.
        int updated = client
            .sql("UPDATE react_state SET state_value = ?, updated_at = CURRENT_TIMESTAMP "
                + "WHERE user_id = ? AND state_key = ?")
            .params(value, user.id(), key)
            .update();
        if (updated == 0) {
            client
                .sql("INSERT INTO react_state (user_id, state_key, state_value, updated_at) "
                    + "VALUES (?, ?, ?, CURRENT_TIMESTAMP)")
                .params(user.id(), key, value)
                .update();
        }
        return Map.of("key", key);
    }

    @DeleteMapping("/{key}")
    public Map<String, Object> delete(AuthUser user, @PathVariable String key) {
        client
            .sql("DELETE FROM react_state WHERE user_id = ? AND state_key = ?")
            .params(user.id(), key)
            .update();
        return Map.of();
    }

    public record UpsertRequest(String value) {
    }
}
