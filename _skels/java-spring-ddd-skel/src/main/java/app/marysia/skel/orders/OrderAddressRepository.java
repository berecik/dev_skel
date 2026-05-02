package app.marysia.skel.orders;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

/**
 * Spring Data JPA repository for the {@code order_addresses} table. One
 * address per order — the {@code order_id} column has a unique constraint
 * so {@link #findByOrderId} returns at most one row.
 */
@Repository
public interface OrderAddressRepository extends JpaRepository<OrderAddress, Long> {

    Optional<OrderAddress> findByOrderId(long orderId);

    long deleteByOrderId(long orderId);
}
