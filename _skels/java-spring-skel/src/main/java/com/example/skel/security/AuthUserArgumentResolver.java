package com.example.skel.security;

import org.springframework.core.MethodParameter;
import org.springframework.stereotype.Component;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;

import jakarta.servlet.http.HttpServletRequest;

/**
 * Adapter that lets controller methods declare an {@link AuthUser}
 * parameter and receive the principal published by
 * {@link JwtAuthInterceptor}. Returns {@code null} when the
 * interceptor did not run for the route — that should never happen
 * because the interceptor is wired against the same paths the
 * controllers expose, but null-safe handling keeps this declarative.
 */
@Component
public class AuthUserArgumentResolver implements HandlerMethodArgumentResolver {

    @Override
    public boolean supportsParameter(MethodParameter parameter) {
        return AuthUser.class.equals(parameter.getParameterType());
    }

    @Override
    public Object resolveArgument(MethodParameter parameter,
                                  ModelAndViewContainer mavContainer,
                                  NativeWebRequest webRequest,
                                  WebDataBinderFactory binderFactory) {
        HttpServletRequest req = webRequest.getNativeRequest(HttpServletRequest.class);
        if (req == null) {
            return null;
        }
        return req.getAttribute(JwtAuthInterceptor.AUTH_USER_ATTR);
    }
}
