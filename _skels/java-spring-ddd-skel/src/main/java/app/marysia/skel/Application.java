package app.marysia.skel;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

/**
 * Application entry point.
 *
 * <p>{@link ConfigurationPropertiesScan} picks up the
 * {@link app.marysia.skel.config.JwtProperties} bean (and any other
 * {@code @ConfigurationProperties} class under
 * {@code app.marysia.skel.config}) so the wrapper-shared JWT environment
 * is injectable everywhere.
 */
@SpringBootApplication
@ConfigurationPropertiesScan("app.marysia.skel.config")
public class Application {

    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
