package app.marysia.skel.auth;

import app.marysia.skel.auth.dto.LoginRequest;
import app.marysia.skel.auth.dto.RegisterRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * Wrapper-shared {@code /api/auth/*} endpoints. Response shapes match
 * the contract every dev_skel backend honours so the React frontend's
 * {@code src/api/auth.ts} works against any of them without a code
 * change:
 *
 * <ul>
 *   <li>{@code POST /api/auth/register} &rarr; {@code 201
 *       { user: { id, username, email }, access, refresh }}</li>
 *   <li>{@code POST /api/auth/login} &rarr; {@code 200
 *       { access, refresh, user_id, username }}</li>
 * </ul>
 *
 * <p>Controller is intentionally thin: it parses the request body, calls
 * a single {@link AuthService} method, and wraps the response in a
 * {@link ResponseEntity} with the correct status code. Error handling
 * is centralised in
 * {@link app.marysia.skel.shared.GlobalExceptionHandler}.
 */
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthService authService;

    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    @PostMapping("/register")
    public ResponseEntity<Map<String, Object>> register(@RequestBody RegisterRequest body) {
        Map<String, Object> resp = authService.register(body);
        return ResponseEntity.status(HttpStatus.CREATED).body(resp);
    }

    @PostMapping("/login")
    public ResponseEntity<Map<String, Object>> login(@RequestBody LoginRequest body) {
        Map<String, Object> resp = authService.login(body);
        return ResponseEntity.ok(resp);
    }
}
