package app.marysia.skel.config;

import app.marysia.skel.security.AuthUserArgumentResolver;
import app.marysia.skel.security.JwtAuthInterceptor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.List;

/**
 * Wires the wrapper-shared JWT auth interceptor into the request
 * pipeline and registers the {@link AuthUserArgumentResolver} so
 * controllers can declare {@code AuthUser} parameters.
 *
 * <p>The interceptor only fires for the JWT-protected resource paths
 * — {@code /api/items/**}, {@code /api/categories/**},
 * {@code /api/state/**}, {@code /api/catalog/**}, and
 * {@code /api/orders/**} — so the unauthenticated
 * {@code /api/auth/register} and {@code /api/auth/login} endpoints
 * stay reachable without a token.
 */
@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    private final JwtAuthInterceptor jwtAuthInterceptor;
    private final AuthUserArgumentResolver authUserArgumentResolver;

    public WebMvcConfig(JwtAuthInterceptor jwtAuthInterceptor,
                        AuthUserArgumentResolver authUserArgumentResolver) {
        this.jwtAuthInterceptor = jwtAuthInterceptor;
        this.authUserArgumentResolver = authUserArgumentResolver;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(jwtAuthInterceptor)
            .addPathPatterns(
                "/api/items", "/api/items/**",
                "/api/categories", "/api/categories/**",
                "/api/state", "/api/state/**",
                "/api/catalog", "/api/catalog/**",
                "/api/orders", "/api/orders/**"
            );
    }

    @Override
    public void addArgumentResolvers(List<HandlerMethodArgumentResolver> resolvers) {
        resolvers.add(authUserArgumentResolver);
    }
}
