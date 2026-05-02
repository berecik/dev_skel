package app.marysia.skel.auth.dto;

/**
 * Request body for {@code POST /api/auth/login}. The {@code username}
 * field accepts either the canonical username or an email address —
 * matching the contract every other dev_skel backend implements.
 */
public record LoginRequest(String username, String password) {
}
