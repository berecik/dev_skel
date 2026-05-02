package app.marysia.skel.auth;

import app.marysia.skel.auth.dto.LoginRequest;
import app.marysia.skel.auth.dto.RegisterRequest;
import app.marysia.skel.shared.ConflictException;
import app.marysia.skel.shared.UnauthorizedException;
import app.marysia.skel.shared.ValidationException;
import app.marysia.skel.users.User;
import app.marysia.skel.users.UserRepository;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

/**
 * Auth-flow orchestrator. Holds {@link UserRepository},
 * {@link PasswordEncoder}, and {@link JwtService} — the controller is
 * a thin HTTP adapter on top of this class.
 *
 * <p>Service methods throw {@code DomainException} subclasses
 * ({@link ValidationException}, {@link ConflictException},
 * {@link UnauthorizedException}) instead of leaking persistence-level
 * exceptions. The {@link app.marysia.skel.shared.GlobalExceptionHandler}
 * advice translates them into the canonical {@code {detail, status}}
 * JSON body.
 */
@Service
public class AuthService {

    private final UserRepository users;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwt;

    public AuthService(UserRepository users,
                       PasswordEncoder passwordEncoder,
                       JwtService jwt) {
        this.users = users;
        this.passwordEncoder = passwordEncoder;
        this.jwt = jwt;
    }

    /**
     * Register a new account and return the
     * {@code { user, access, refresh }} response body the React frontend
     * expects from {@code POST /api/auth/register}.
     */
    public Map<String, Object> register(RegisterRequest body) {
        if (body == null || body.username() == null || body.username().isBlank()) {
            throw new ValidationException("username cannot be empty");
        }
        if (body.password() == null || body.password().length() < 6) {
            throw new ValidationException("password must be at least 6 characters");
        }
        if (body.passwordConfirm() != null
            && !body.passwordConfirm().equals(body.password())) {
            throw new ValidationException("password and password_confirm do not match");
        }
        if (users.findByUsername(body.username()).isPresent()) {
            throw new ConflictException("user '" + body.username() + "' already exists");
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
        return resp;
    }

    /**
     * Authenticate the user and return the
     * {@code { access, refresh, user_id, username }} response body the
     * React frontend expects from {@code POST /api/auth/login}.
     */
    public Map<String, Object> login(LoginRequest body) {
        if (body == null || body.username() == null || body.password() == null) {
            throw new UnauthorizedException("invalid username or password");
        }
        Optional<User> found = body.username().contains("@")
            ? users.findByEmail(body.username())
            : users.findByUsername(body.username());
        if (found.isEmpty()) {
            throw new UnauthorizedException("invalid username or password");
        }
        User u = found.get();
        if (!passwordEncoder.matches(body.password(), u.getPasswordHash())) {
            throw new UnauthorizedException("invalid username or password");
        }

        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("access", jwt.mintAccessToken(u.getId()));
        resp.put("refresh", jwt.mintRefreshToken(u.getId()));
        resp.put("user_id", u.getId());
        resp.put("username", u.getUsername());
        return resp;
    }
}
