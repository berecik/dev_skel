package com.example.skel.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Wrapper-shared JWT configuration.
 *
 * <p>Reads {@code app.jwt.*} properties from {@code application.properties},
 * which in turn map onto the wrapper-shared environment variables
 * {@code JWT_SECRET}, {@code JWT_ALGORITHM}, {@code JWT_ISSUER},
 * {@code JWT_ACCESS_TTL}, and {@code JWT_REFRESH_TTL} defined in
 * {@code <wrapper>/.env}.
 *
 * <p>Registered via {@code @ConfigurationPropertiesScan} on
 * {@link com.example.skel.Application}; inject the bean wherever you need
 * to mint or verify a JWT. Every service in the wrapper sees the same
 * secret + algorithm so a token issued by one service is accepted by
 * every other service that follows the same convention.
 */
@ConfigurationProperties(prefix = "app.jwt")
public class JwtProperties {

    private String secret = "change-me-32-bytes-of-random-data";
    private String algorithm = "HS256";
    private String issuer = "devskel";
    private long accessTtl = 3600L;
    private long refreshTtl = 604800L;

    public String getSecret() {
        return secret;
    }

    public void setSecret(String secret) {
        this.secret = secret;
    }

    public String getAlgorithm() {
        return algorithm;
    }

    public void setAlgorithm(String algorithm) {
        this.algorithm = algorithm;
    }

    public String getIssuer() {
        return issuer;
    }

    public void setIssuer(String issuer) {
        this.issuer = issuer;
    }

    public long getAccessTtl() {
        return accessTtl;
    }

    public void setAccessTtl(long accessTtl) {
        this.accessTtl = accessTtl;
    }

    public long getRefreshTtl() {
        return refreshTtl;
    }

    public void setRefreshTtl(long refreshTtl) {
        this.refreshTtl = refreshTtl;
    }
}
