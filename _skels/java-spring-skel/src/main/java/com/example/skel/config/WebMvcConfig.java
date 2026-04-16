package com.example.skel.config;

import com.example.skel.security.AuthUserArgumentResolver;
import com.example.skel.security.JwtAuthInterceptor;
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
 * — {@code /api/items/**} and {@code /api/state/**} — so the
 * unauthenticated {@code /api/auth/register} and {@code /api/auth/login}
 * endpoints stay reachable without a token.
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
            .addPathPatterns("/api/items", "/api/items/**", "/api/state", "/api/state/**");
    }

    @Override
    public void addArgumentResolvers(List<HandlerMethodArgumentResolver> resolvers) {
        resolvers.add(authUserArgumentResolver);
    }
}
