package app.marysia.skel.security;

/**
 * Authenticated principal published into the request attribute by
 * {@link JwtAuthInterceptor}. Controllers retrieve it via the
 * {@link AuthUserArgumentResolver} so the JWT-derived user id +
 * username are available as a plain method argument.
 */
public record AuthUser(long id, String username) {
}
