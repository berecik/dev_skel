package app.marysia.skel.repository;

import app.marysia.skel.model.OrderRecord;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * Spring Data JPA repository for the wrapper-shared {@code orders}
 * table. The list endpoint orders by id descending (newest first) to
 * preserve the pre-JPA SQL contract.
 */
@Repository
public interface OrderRepository extends JpaRepository<OrderRecord, Long> {

    List<OrderRecord> findAllByUserIdOrderByIdDesc(long userId);
}
