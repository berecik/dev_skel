package app.marysia.skel.catalog;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * Spring Data JPA repository for the {@code catalog_items} table.
 */
@Repository
public interface CatalogItemRepository extends JpaRepository<CatalogItem, Long> {

    List<CatalogItem> findAllByOrderByIdAsc();
}
