package app.marysia.skel;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * Top-level discovery routes ({@code /} and {@code /health}). Lives at
 * the root package level rather than inside a feature module because
 * neither endpoint is a domain resource — they're cross-cutting service
 * metadata. Both routes are unauthenticated by design (the
 * {@code JwtAuthInterceptor} in {@link app.marysia.skel.config.WebMvcConfig}
 * is wired to {@code /api/**} only).
 */
@RestController
public class RootController {

    @Value("${spring.application.name:java-spring-skel}")
    private String projectName;

    @Value("${app.version:1.0.0}")
    private String version;

    @GetMapping("/")
    public Map<String, String> root() {
        return Map.of(
                "project", projectName,
                "version", version,
                "framework", "Spring Boot",
                "status", "running"
        );
    }

    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of("status", "healthy");
    }
}
