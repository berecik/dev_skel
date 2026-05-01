package app.marysia.skel.repository;

import app.marysia.skel.model.Item;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * Spring Data JPA repository for the wrapper-shared {@code items} table.
 * The {@code findAllByOrderByCreatedAtDescIdDesc} derived method
 * preserves the pre-JPA SQL ordering ({@code ORDER BY created_at DESC,
 * id DESC}) the React frontend relies on for "newest first" lists.
 */
@Repository
public interface ItemRepository extends JpaRepository<Item, Long> {

    List<Item> findAllByOrderByCreatedAtDescIdDesc();
}
