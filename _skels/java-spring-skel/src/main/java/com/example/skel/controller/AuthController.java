package com.example.skel.controller;

import com.example.skel.security.JwtService;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.sql.PreparedStatement;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;

/**
 * Wrapper-shared {@code /api/auth/*} endpoints. Response shapes match
 * the contract every dev_skel backend honours so the React frontend's
 * {@code src/api/auth.ts} works against any of them without a code
 * change:
 *
 * <ul>
 *   <li>{@code POST /api/auth/register} → {@code 201
 *       { user: { id, username, email }, access, refresh }}</li>
 *   <li>{@code POST /api/auth/login} → {@code 200
 *       { access, refresh, user_id, username }}</li>
 * </ul>
 */
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final JdbcTemplate jdbc;
    private final JdbcClient client;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwt;

    public AuthController(JdbcTemplate jdbc,
                          PasswordEncoder passwordEncoder,
                          JwtService jwt) {
        this.jdbc = jdbc;
        this.client = JdbcClient.create(jdbc);
        this.passwordEncoder = passwordEncoder;
        this.jwt = jwt;
    }

    @PostMapping("/register")
    public ResponseEntity<Map<String, Object>> register(@RequestBody RegisterRequest body) {
        if (body == null || body.username() == null || body.username().isBlank()) {
            return error(HttpStatus.BAD_REQUEST, "username cannot be empty");
        }
        if (body.password() == null || body.password().length() < 6) {
            return error(HttpStatus.BAD_REQUEST, "password must be at least 6 characters");
        }
        if (body.passwordConfirm() != null && !body.passwordConfirm().equals(body.password())) {
            return error(HttpStatus.BAD_REQUEST, "password and password_confirm do not match");
        }

        Long existing = lookupId(body.username());
        if (existing != null) {
            return error(HttpStatus.CONFLICT, "user '" + body.username() + "' already exists");
        }

        String hash = passwordEncoder.encode(body.password());
        var keyHolder = new org.springframework.jdbc.support.GeneratedKeyHolder();
        jdbc.update(connection -> {
            // Pass `new String[]{"id"}` instead of
            // `Statement.RETURN_GENERATED_KEYS` so H2 only returns the
            // `id` column (otherwise it returns id + created_at and
            // `KeyHolder.getKey()` raises about a multi-column result).
            PreparedStatement ps = connection.prepareStatement(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                new String[]{"id"}
            );
            ps.setString(1, body.username());
            ps.setString(2, body.email() == null ? "" : body.email());
            ps.setString(3, hash);
            return ps;
        }, keyHolder);
        long newId = Objects.requireNonNull(keyHolder.getKey(),
            "INSERT did not return a generated key").longValue();

        Map<String, Object> userOut = new LinkedHashMap<>();
        userOut.put("id", newId);
        userOut.put("username", body.username());
        userOut.put("email", body.email() == null ? "" : body.email());

        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("user", userOut);
        resp.put("access", jwt.mintAccessToken(newId));
        resp.put("refresh", jwt.mintRefreshToken(newId));
        return ResponseEntity.status(HttpStatus.CREATED).body(resp);
    }

    @PostMapping("/login")
    public ResponseEntity<Map<String, Object>> login(@RequestBody LoginRequest body) {
        if (body == null || body.username() == null || body.password() == null) {
            return error(HttpStatus.UNAUTHORIZED, "invalid username or password");
        }
        String sql = body.username().contains("@")
            ? "SELECT id, username, password_hash FROM users WHERE email = ?"
            : "SELECT id, username, password_hash FROM users WHERE username = ?";
        Map<String, Object> row;
        try {
            row = client
                .sql(sql)
                .param(body.username())
                .query()
                .singleRow();
        } catch (EmptyResultDataAccessException e) {
            return error(HttpStatus.UNAUTHORIZED, "invalid username or password");
        }

        long id = ((Number) row.get("id")).longValue();
        String username = (String) row.get("username");
        String storedHash = (String) row.get("password_hash");
        if (!passwordEncoder.matches(body.password(), storedHash)) {
            return error(HttpStatus.UNAUTHORIZED, "invalid username or password");
        }

        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("access", jwt.mintAccessToken(id));
        resp.put("refresh", jwt.mintRefreshToken(id));
        resp.put("user_id", id);
        resp.put("username", username);
        return ResponseEntity.ok(resp);
    }

    private Long lookupId(String username) {
        try {
            return client
                .sql("SELECT id FROM users WHERE username = ?")
                .param(username)
                .query(Long.class)
                .single();
        } catch (EmptyResultDataAccessException e) {
            return null;
        }
    }

    private ResponseEntity<Map<String, Object>> error(HttpStatus status, String detail) {
        return ResponseEntity.status(status).body(Map.of(
            "detail", detail,
            "status", status.value()
        ));
    }

    public record RegisterRequest(
        String username,
        String email,
        String password,
        String passwordConfirm
    ) {
    }

    public record LoginRequest(String username, String password) {
    }
}
