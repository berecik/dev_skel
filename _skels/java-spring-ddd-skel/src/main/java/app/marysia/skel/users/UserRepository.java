package app.marysia.skel.users;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

/**
 * Spring Data JPA repository for the wrapper-shared {@code users}
 * table. Lookup-by-username and lookup-by-email back the
 * {@code /api/auth/login} endpoint's two acceptance paths.
 */
@Repository
public interface UserRepository extends JpaRepository<User, Long> {

    Optional<User> findByUsername(String username);

    Optional<User> findByEmail(String email);
}
