package app.marysia.skel.repository;

import app.marysia.skel.model.Category;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * Spring Data JPA repository for the wrapper-shared {@code categories}
 * table. CRUD methods come from {@link JpaRepository}; the only custom
 * member is {@link #findByName} for the django-bolt parity check.
 */
@Repository
public interface CategoryRepository extends JpaRepository<Category, Long> {

    /** Returns every category ordered by id ascending (matches the
     *  pre-JPA SQL contract used by the React frontend). */
    List<Category> findAllByOrderByIdAsc();

    Optional<Category> findByName(String name);
}
