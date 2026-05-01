package app.marysia.skel.config;

import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

import app.marysia.skel.model.User;
import app.marysia.skel.repository.UserRepository;

/**
 * Idempotent default-account seed for the wrapper-shared backend stack.
 *
 * <p>Replaces the seed half of the (now-deleted) {@code SchemaInitializer}.
 * Schema bootstrap itself is now handled by Hibernate's
 * {@code spring.jpa.hibernate.ddl-auto=update} reading the
 * {@code @Entity} annotations on application startup, so this bean
 * only has to ensure the canonical {@code user} / {@code admin} pair
 * exists for the cross-stack tests + the django-bolt parity check.
 *
 * <p>The seeding runs from {@link PostConstruct} on a {@link Component}
 * — NOT from an {@code ApplicationRunner} — so the bcrypt-heavy
 * {@code encoder.encode(...)} calls finish during context refresh,
 * BEFORE the embedded Tomcat starts accepting traffic. The earlier
 * runner-based variant raced the cross-stack login probe (which fires
 * within ~100 ms of the {@code "Started Application"} log line, and
 * bcrypt's default cost of 10 takes ~250 ms per call).
 *
 * <p>Credentials come from the wrapper-shared {@code USER_*} /
 * {@code SUPERUSER_*} env vars (defaults: {@code user/secret} and
 * {@code admin/secret}).
 */
@Component
public class DefaultUserSeeder {

    private static final Logger log = LoggerFactory.getLogger(DefaultUserSeeder.class);

    private final UserRepository users;
    private final PasswordEncoder encoder;

    public DefaultUserSeeder(UserRepository users, PasswordEncoder encoder) {
        this.users = users;
        this.encoder = encoder;
    }

    @PostConstruct
    public void seedDefaults() {
        seed(env("USER_LOGIN", "user"),
             env("USER_EMAIL", "user@example.com"),
             env("USER_PASSWORD", "secret"),
             false);
        seed(env("SUPERUSER_LOGIN", "admin"),
             env("SUPERUSER_EMAIL", "admin@example.com"),
             env("SUPERUSER_PASSWORD", "secret"),
             true);
    }

    private void seed(String username, String email, String password, boolean superuser) {
        if (users.findByUsername(username).isPresent()) {
            log.info("[seed] Default user '{}' already exists", username);
            return;
        }
        User u = new User(username, email, encoder.encode(password), superuser);
        users.save(u);
        log.info("[seed] Created default user '{}'", username);
    }

    private static String env(String key, String fallback) {
        String val = System.getenv(key);
        return (val != null && !val.isBlank()) ? val : fallback;
    }
}
