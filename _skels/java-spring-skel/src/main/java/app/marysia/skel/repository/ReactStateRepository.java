package app.marysia.skel.repository;

import app.marysia.skel.model.ReactState;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * Spring Data JPA repository for the per-user {@code react_state} KV
 * slice. Composite uniqueness on {@code (user_id, state_key)} powers
 * the upsert path.
 */
@Repository
public interface ReactStateRepository extends JpaRepository<ReactState, Long> {

    Optional<ReactState> findByUserIdAndKey(long userId, String key);

    List<ReactState> findAllByUserIdOrderByKeyAsc(long userId);

    long deleteByUserIdAndKey(long userId, String key);
}
