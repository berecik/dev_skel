package app.marysia.skel.controller;

import app.marysia.skel.model.User;
import app.marysia.skel.repository.UserRepository;
import app.marysia.skel.security.JwtService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

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

    private final UserRepository users;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwt;

    public AuthController(UserRepository users,
                          PasswordEncoder passwordEncoder,
                          JwtService jwt) {
        this.users = users;
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

        if (users.findByUsername(body.username()).isPresent()) {
            return error(HttpStatus.CONFLICT, "user '" + body.username() + "' already exists");
        }

        User u = new User(
            body.username(),
            body.email() == null ? "" : body.email(),
            passwordEncoder.encode(body.password()),
            false
        );
        u = users.save(u);

        Map<String, Object> userOut = new LinkedHashMap<>();
        userOut.put("id", u.getId());
        userOut.put("username", u.getUsername());
        userOut.put("email", u.getEmail());

        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("user", userOut);
        resp.put("access", jwt.mintAccessToken(u.getId()));
        resp.put("refresh", jwt.mintRefreshToken(u.getId()));
        return ResponseEntity.status(HttpStatus.CREATED).body(resp);
    }

    @PostMapping("/login")
    public ResponseEntity<Map<String, Object>> login(@RequestBody LoginRequest body) {
        if (body == null || body.username() == null || body.password() == null) {
            return error(HttpStatus.UNAUTHORIZED, "invalid username or password");
        }
        Optional<User> found = body.username().contains("@")
            ? users.findByEmail(body.username())
            : users.findByUsername(body.username());
        if (found.isEmpty()) {
            return error(HttpStatus.UNAUTHORIZED, "invalid username or password");
        }
        User u = found.get();
        if (!passwordEncoder.matches(body.password(), u.getPasswordHash())) {
            return error(HttpStatus.UNAUTHORIZED, "invalid username or password");
        }

        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("access", jwt.mintAccessToken(u.getId()));
        resp.put("refresh", jwt.mintRefreshToken(u.getId()));
        resp.put("user_id", u.getId());
        resp.put("username", u.getUsername());
        return ResponseEntity.ok(resp);
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
