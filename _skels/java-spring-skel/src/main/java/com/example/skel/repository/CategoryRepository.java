package com.example.skel.repository;

import com.example.skel.model.Category;
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
 * Plain-JDBC repository for the wrapper-shared {@code categories} table.
 *
 * <p>We intentionally avoid {@code spring-boot-starter-data-jpa} so the
 * same code works against the wrapper's default SQLite, an H2 in-memory
 * fallback, or Postgres without juggling Hibernate dialects.
 */
@Repository
public class CategoryRepository {

    private static final DateTimeFormatter ISO =
        DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'");

    private static final RowMapper<Category> MAPPER = (rs, _row) -> new Category(
        rs.getLong("id"),
        rs.getString("name"),
        rs.getString("description"),
        rs.getString("created_at"),
        rs.getString("updated_at")
    );

    private final JdbcTemplate jdbc;
    private final JdbcClient client;

    public CategoryRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
        this.client = JdbcClient.create(jdbc);
    }

    public List<Category> findAll() {
        return client
            .sql("SELECT id, name, description, created_at, updated_at "
                + "FROM categories ORDER BY id ASC")
            .query(MAPPER)
            .list();
    }

    public Optional<Category> findById(long id) {
        try {
            return Optional.of(
                client
                    .sql("SELECT id, name, description, created_at, updated_at "
                        + "FROM categories WHERE id = ?")
                    .param(id)
                    .query(MAPPER)
                    .single()
            );
        } catch (EmptyResultDataAccessException e) {
            return Optional.empty();
        }
    }

    /**
     * Insert a new category and return the persisted row (with its auto-
     * assigned id and timestamps).
     */
    public Category insert(String name, String description) {
        String now = nowIso();
        var keyHolder = new org.springframework.jdbc.support.GeneratedKeyHolder();
        jdbc.update(connection -> {
            PreparedStatement ps = connection.prepareStatement(
                "INSERT INTO categories (name, description, created_at, updated_at) "
                    + "VALUES (?, ?, ?, ?)",
                new String[]{"id"}
            );
            ps.setString(1, name);
            ps.setString(2, description);
            ps.setString(3, now);
            ps.setString(4, now);
            return ps;
        }, keyHolder);
        Number key = Objects.requireNonNull(keyHolder.getKey(), "INSERT did not return a generated key");
        return new Category(key.longValue(), name, description, now, now);
    }

    /**
     * Update name and description of an existing category.
     * Returns the refreshed row, or {@link Optional#empty()} when
     * the row no longer exists.
     */
    public Optional<Category> update(long id, String name, String description) {
        String now = nowIso();
        int updated = jdbc.update(
            "UPDATE categories SET name = ?, description = ?, updated_at = ? WHERE id = ?",
            name, description, now, id
        );
        if (updated == 0) {
            return Optional.empty();
        }
        return findById(id);
    }

    /**
     * Delete a category by id. Returns {@code true} if the row existed.
     */
    public boolean deleteById(long id) {
        int deleted = jdbc.update("DELETE FROM categories WHERE id = ?", id);
        return deleted > 0;
    }

    private static String nowIso() {
        return OffsetDateTime.now(ZoneOffset.UTC).format(ISO);
    }
}
