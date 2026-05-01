package app.marysia.skel.security;

import app.marysia.skel.model.User;
import app.marysia.skel.repository.UserRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

/**
 * Lightweight JWT bearer-auth interceptor. Registered against the
 * {@code /api/items/**}, {@code /api/categories/**}, and
 * {@code /api/state/**} URL patterns by
 * {@link app.marysia.skel.config.WebMvcConfig}.
 *
 * <p>Failed auth writes a JSON 401 body matching the contract every
 * other dev_skel backend honours so the React frontend's
 * {@code AuthError} branch fires consistently across stacks.
 *
 * <p>The authenticated user is published into the request attribute
 * under {@link #AUTH_USER_ATTR} so {@link AuthUserArgumentResolver}
 * can hand it to controller methods that declare an {@link AuthUser}
 * parameter.
 */
@Component
public class JwtAuthInterceptor implements HandlerInterceptor {

    public static final String AUTH_USER_ATTR = "app.marysia.skel.security.authUser";

    private final JwtService jwtService;
    private final UserRepository users;
    private final ObjectMapper mapper;

    public JwtAuthInterceptor(JwtService jwtService, UserRepository users, ObjectMapper mapper) {
        this.jwtService = jwtService;
        this.users = users;
        this.mapper = mapper;
    }

    @Override
    public boolean preHandle(HttpServletRequest request,
                             HttpServletResponse response,
                             Object handler) throws Exception {
        String header = request.getHeader("Authorization");
        if (header == null || !header.startsWith("Bearer ")) {
            return reject(response, "missing or malformed Authorization header");
        }
        String token = header.substring("Bearer ".length()).trim();

        JwtService.Verified verified;
        try {
            verified = jwtService.verify(token);
        } catch (Exception e) {
            return reject(response, "invalid or expired token");
        }
        if (verified.isRefreshToken()) {
            return reject(response, "refresh token cannot authenticate this request");
        }

        // Check the user still exists; deletion mid-session must surface as 401.
        Optional<User> found;
        try {
            found = users.findById(verified.userId());
        } catch (DataAccessException e) {
            return reject(response, "user lookup failed");
        }
        if (found.isEmpty()) {
            return reject(response, "user no longer exists");
        }
        User u = found.get();
        request.setAttribute(AUTH_USER_ATTR, new AuthUser(u.getId(), u.getUsername()));
        return true;
    }

    private boolean reject(HttpServletResponse response, String detail) throws java.io.IOException {
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType("application/json");
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("detail", detail);
        body.put("status", HttpServletResponse.SC_UNAUTHORIZED);
        response.getWriter().write(mapper.writeValueAsString(body));
        return false;
    }
}
