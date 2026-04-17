package com.example.skel.repository;

import com.example.skel.model.Item;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import java.sql.PreparedStatement;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Objects;
import java.util.Optional;

/**
 * Plain-JDBC repository for the wrapper-shared {@code items} table.
 *
 * <p>We intentionally avoid {@code spring-boot-starter-data-jpa} so the
 * same code works against the wrapper's default SQLite, an H2 in-memory
 * fallback, or Postgres without juggling Hibernate dialects.
 */
@Repository
public class ItemRepository {

    private static final DateTimeFormatter ISO =
        DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'");

    private static final RowMapper<Item> MAPPER = (rs, _row) -> {
        long catId = rs.getLong("category_id");
        Long categoryId = rs.wasNull() ? null : catId;
        return new Item(
            rs.getLong("id"),
            rs.getString("name"),
            rs.getString("description"),
            rs.getBoolean("is_completed"),
            categoryId,
            rs.getString("created_at"),
            rs.getString("updated_at")
        );
    };

    private final JdbcTemplate jdbc;
    private final JdbcClient client;

    public ItemRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
        this.client = JdbcClient.create(jdbc);
    }

    public List<Item> findAll() {
        return client
            .sql("SELECT id, name, description, is_completed, category_id, created_at, updated_at "
                + "FROM items ORDER BY created_at DESC, id DESC")
            .query(MAPPER)
            .list();
    }

    public Optional<Item> findById(long id) {
        try {
            return Optional.of(
                client
                    .sql("SELECT id, name, description, is_completed, category_id, created_at, updated_at "
                        + "FROM items WHERE id = ?")
                    .param(id)
                    .query(MAPPER)
                    .single()
            );
        } catch (EmptyResultDataAccessException e) {
            return Optional.empty();
        }
    }

    /**
     * Insert a new item and return the persisted row (with its auto-
     * assigned id and timestamps). Uses {@link java.sql.Statement#RETURN_GENERATED_KEYS}
     * because SQLite + H2 + Postgres all support it via JDBC, unlike
     * {@code RETURNING ...} which has divergent dialects.
     */
    public Item insert(String name, String description, boolean isCompleted, Long categoryId) {
        String now = nowIso();
        var keyHolder = new org.springframework.jdbc.support.GeneratedKeyHolder();
        jdbc.update(connection -> {
            // Pass `new String[]{"id"}` instead of
            // `Statement.RETURN_GENERATED_KEYS` because H2 returns
            // every column populated by defaults (id + created_at +
            // updated_at), and `KeyHolder.getKey()` then complains
            // about a multi-column result. Naming `id` explicitly
            // works for SQLite, H2, and Postgres.
            PreparedStatement ps = connection.prepareStatement(
                "INSERT INTO items (name, description, is_completed, category_id, created_at, updated_at) "
                    + "VALUES (?, ?, ?, ?, ?, ?)",
                new String[]{"id"}
            );
            ps.setString(1, name);
            ps.setString(2, description);
            ps.setBoolean(3, isCompleted);
            if (categoryId != null) {
                ps.setLong(4, categoryId);
            } else {
                ps.setNull(4, java.sql.Types.BIGINT);
            }
            ps.setString(5, now);
            ps.setString(6, now);
            return ps;
        }, keyHolder);
        Number key = Objects.requireNonNull(keyHolder.getKey(), "INSERT did not return a generated key");
        return new Item(key.longValue(), name, description, isCompleted, categoryId, now, now);
    }

    /**
     * Mark an item as completed. Returns the refreshed row, or
     * {@link Optional#empty()} when the row no longer exists.
     */
    public Optional<Item> markCompleted(long id) {
        String now = nowIso();
        int updated = jdbc.update(
            "UPDATE items SET is_completed = ?, updated_at = ? WHERE id = ?",
            true, now, id
        );
        if (updated == 0) {
            return Optional.empty();
        }
        return findById(id);
    }

    private static String nowIso() {
        return OffsetDateTime.now(ZoneOffset.UTC).format(ISO);
    }
}
