package app.marysia.skel.auth.dto;

/**
 * Request body for {@code POST /api/auth/register}. Fields are
 * deliberately nullable on the wire so the service layer can produce
 * the canonical {@code 400 detail} message instead of a generic
 * Jackson failure.
 */
public record RegisterRequest(
    String username,
    String email,
    String password,
    String passwordConfirm
) {
}
