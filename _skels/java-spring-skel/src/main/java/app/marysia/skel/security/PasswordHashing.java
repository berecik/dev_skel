package app.marysia.skel.security;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;

/**
 * Exposes a single shared {@link PasswordEncoder} bean (BCrypt with the
 * default cost of 10) so {@code AuthController} can register and
 * authenticate users without depending on the full
 * {@code spring-boot-starter-security} stack.
 */
@Configuration
public class PasswordHashing {

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }
}
