package app.marysia.skel.repository;

import app.marysia.skel.model.OrderLine;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * Spring Data JPA repository for the {@code order_lines} table.
 */
@Repository
public interface OrderLineRepository extends JpaRepository<OrderLine, Long> {

    List<OrderLine> findAllByOrderIdOrderByIdAsc(long orderId);

    long countByOrderId(long orderId);

    long deleteByIdAndOrderId(long id, long orderId);
}
