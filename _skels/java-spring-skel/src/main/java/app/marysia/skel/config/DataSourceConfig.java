package app.marysia.skel.config;

import com.zaxxer.hikari.HikariDataSource;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.jdbc.DataSourceProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;

import javax.sql.DataSource;
import java.io.File;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * Wrapper-aware {@link DataSource} factory.
 *
 * <p>Spring Boot's auto-configured {@code HikariDataSource} happily
 * forwards whatever JDBC URL it receives to the driver. The wrapper-
 * shared {@code <wrapper>/.env} ships
 * {@code SPRING_DATASOURCE_URL=jdbc:sqlite:_shared/db.sqlite3} —
 * a path that is relative to the <em>wrapper</em> directory by
 * convention, but the JVM cwd is the <em>service</em> directory, so
 * the SQLite driver would create a fresh database inside the service.
 *
 * <p>This bean intercepts the URL <em>before</em> Hikari opens its
 * first connection and rewrites any {@code jdbc:sqlite:<relative>}
 * URL into {@code jdbc:sqlite:<wrapper>/<relative>} so every service
 * that points at the same relative path lands on the same SQLite file.
 * Other JDBC URLs ({@code jdbc:h2:...}, {@code jdbc:postgresql://...},
 * absolute SQLite URLs) pass through unchanged.
 */
@Configuration
public class DataSourceConfig {

    private static final Logger log = LoggerFactory.getLogger(DataSourceConfig.class);

    /**
     * Override Spring Boot's auto-configured {@link DataSource} so we
     * can rewrite the SQLite URL if needed before Hikari opens its
     * first connection.
     *
     * <p>Spring Boot already provides a {@link DataSourceProperties}
     * bean populated from the standard {@code spring.datasource.*}
     * properties — we inject that one rather than re-declaring it (a
     * second {@code @Bean} of the same type would collide with the
     * auto-configured one and fail context startup).
     */
    @Bean
    @Primary
    public DataSource dataSource(DataSourceProperties properties) {
        String originalUrl = properties.getUrl();
        String resolvedUrl = resolveSqliteUrl(originalUrl);

        if (!resolvedUrl.equals(originalUrl)) {
            log.info(
                "Rewrote relative SQLite URL '{}' to wrapper-anchored '{}'",
                originalUrl,
                resolvedUrl
            );
        }

        HikariDataSource hikari = properties
            .initializeDataSourceBuilder()
            .type(HikariDataSource.class)
            .url(resolvedUrl)
            .build();
        return hikari;
    }

    /**
     * Translate a {@code jdbc:sqlite:<relative-path>} URL into
     * {@code jdbc:sqlite:<wrapper>/<relative-path>}. Returns the
     * input unchanged for non-SQLite URLs and for SQLite URLs whose
     * path component is already absolute or in-memory.
     *
     * <p>Package-private so it can be unit-tested without spinning up
     * a Spring context.
     */
    static String resolveSqliteUrl(String url) {
        if (url == null) {
            return null;
        }
        final String prefix = "jdbc:sqlite:";
        if (!url.startsWith(prefix)) {
            return url;
        }
        String pathPart = url.substring(prefix.length());
        // ":memory:" or "" → leave it alone.
        if (pathPart.isEmpty() || pathPart.startsWith(":")) {
            return url;
        }
        File pathFile = new File(pathPart);
        if (pathFile.isAbsolute()) {
            return url;
        }
        Path wrapperDir = wrapperDirectory();
        if (wrapperDir == null) {
            return url;
        }
        Path resolved = wrapperDir.resolve(pathPart).toAbsolutePath().normalize();
        // Make sure the parent directory exists so SQLite can create
        // the file on first connect (Hikari fails with `file not found`
        // when the parent is missing).
        try {
            File parent = resolved.toFile().getParentFile();
            if (parent != null && !parent.exists()) {
                //noinspection ResultOfMethodCallIgnored
                parent.mkdirs();
            }
        } catch (Exception ignore) {
            // Best-effort. If we cannot create the parent dir the
            // driver will surface a clear error on first connect.
        }
        return prefix + resolved;
    }

    /**
     * The wrapper directory is the parent of the service (cwd) by
     * dev_skel convention. Returns {@code null} when the JVM is not
     * running inside a wrapper (e.g. in a JAR distribution where the
     * cwd has no parent).
     */
    private static Path wrapperDirectory() {
        Path cwd = Paths.get("").toAbsolutePath();
        Path parent = cwd.getParent();
        return parent;
    }
}
