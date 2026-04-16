package com.example.skel.security;

import com.example.skel.config.JwtProperties;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.time.Instant;
import java.util.Date;
import java.util.Map;

/**
 * Mint + verify HS-family JWT access / refresh tokens using the
 * wrapper-shared {@link JwtProperties}. Token shape matches every
 * other dev_skel backend: {@code iss=devskel}, {@code sub=<user id>},
 * optional {@code token_type=refresh}.
 */
@Service
public class JwtService {

    private final JwtProperties props;
    private final SecretKey signingKey;

    public JwtService(JwtProperties props) {
        this.props = props;
        // jjwt requires HS256 keys to be at least 256 bits. The
        // wrapper-shared default is 32 ASCII bytes (= 256 bits) so the
        // happy path works as-is; when the user supplies a shorter
        // secret we pad it on the fly so dev environments don't crash
        // at boot.
        byte[] secretBytes = padToMinimum(props.getSecret().getBytes(), 32);
        this.signingKey = Keys.hmacShaKeyFor(secretBytes);
    }

    /** Mint an access token for {@code userId} (TTL = {@code app.jwt.access-ttl}). */
    public String mintAccessToken(long userId) {
        return mint(userId, props.getAccessTtl(), null);
    }

    /** Mint a refresh token for {@code userId} (TTL = {@code app.jwt.refresh-ttl}). */
    public String mintRefreshToken(long userId) {
        return mint(userId, props.getRefreshTtl(), "refresh");
    }

    private String mint(long userId, long ttlSeconds, String tokenType) {
        Instant now = Instant.now();
        var builder = Jwts.builder()
            .issuer(props.getIssuer())
            .subject(Long.toString(userId))
            .issuedAt(Date.from(now))
            .expiration(Date.from(now.plusSeconds(ttlSeconds)))
            .signWith(signingKey);
        if (tokenType != null) {
            builder.claim("token_type", tokenType);
        }
        return builder.compact();
    }

    /**
     * Verify a token and return the {@code (userId, claims)} pair.
     * Throws {@link JwtException} on any failure (expired, bad
     * signature, wrong issuer, malformed) — callers translate to 401.
     */
    public Verified verify(String token) {
        Claims claims = Jwts.parser()
            .verifyWith(signingKey)
            .requireIssuer(props.getIssuer())
            .build()
            .parseSignedClaims(token)
            .getPayload();
        long userId;
        try {
            userId = Long.parseLong(claims.getSubject());
        } catch (NumberFormatException e) {
            throw new JwtException("malformed sub claim");
        }
        return new Verified(userId, Map.copyOf(claims));
    }

    private static byte[] padToMinimum(byte[] src, int minLen) {
        if (src.length >= minLen) {
            return src;
        }
        byte[] out = new byte[minLen];
        System.arraycopy(src, 0, out, 0, src.length);
        // Trailing zero padding is fine — the secret is never reused
        // across services with shorter strings (the wrapper ships a
        // 32-byte default so the production path doesn't touch this).
        return out;
    }

    public record Verified(long userId, Map<String, Object> claims) {
        public boolean isRefreshToken() {
            return "refresh".equals(claims.get("token_type"));
        }
    }
}
