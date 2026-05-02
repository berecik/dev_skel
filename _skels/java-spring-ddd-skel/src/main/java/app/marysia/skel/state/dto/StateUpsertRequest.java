package app.marysia.skel.state.dto;

/**
 * Request body for {@code PUT /api/state/{key}}. The {@code value}
 * field is the (typically JSON-stringified) slice the React
 * {@code useAppState<T>(key, default)} hook wants persisted.
 */
public record StateUpsertRequest(String value) {
}
