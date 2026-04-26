/**
 * `OrderList` — renders the user's orders showing id, status, and
 * created_at. Expandable rows show full order detail (lines + address).
 *
 * Receives the resolved `useOrders` hook fields from the parent so the
 * parent can share a single cache with `<OrderForm />`.
 */

import { useCallback, useState, type ReactElement } from 'react';

import { type Order, type OrderDetail } from '../api/orders';

export interface OrderListProps {
  orders: Order[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  getOrderDetail: (id: number) => Promise<OrderDetail>;
  submitOrder: (id: number) => Promise<void>;
}

export default function OrderList({
  orders,
  loading,
  error,
  refresh,
  getOrderDetail,
  submitOrder,
}: OrderListProps): ReactElement {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<OrderDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const handleToggle = useCallback(
    async (id: number): Promise<void> => {
      if (expandedId === id) {
        setExpandedId(null);
        setDetail(null);
        return;
      }
      setExpandedId(id);
      setDetailLoading(true);
      try {
        const d = await getOrderDetail(id);
        setDetail(d);
      } catch {
        setDetail(null);
      } finally {
        setDetailLoading(false);
      }
    },
    [expandedId, getOrderDetail],
  );

  const handleSubmit = useCallback(
    async (id: number): Promise<void> => {
      try {
        await submitOrder(id);
        await refresh();
      } catch {
        // Error surfaces via parent hook's error field.
      }
    },
    [submitOrder, refresh],
  );

  if (loading && orders.length === 0) {
    return <p className="status">Loading orders...</p>;
  }

  return (
    <section className="order-list">
      <header>
        <h2>Orders ({orders.length})</h2>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading}
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </header>

      {error && <p className="error">Error: {error}</p>}

      {orders.length === 0 ? (
        <p className="empty">No orders yet — create one above.</p>
      ) : (
        <ul>
          {orders.map((order) => (
            <li key={order.id} className="order-row">
              <div className="order-summary">
                <button
                  type="button"
                  className="order-toggle"
                  onClick={() => void handleToggle(order.id)}
                >
                  Order #{order.id}
                </button>
                <span className="order-status">{order.status}</span>
                <small>{order.created_at}</small>
                {order.status === 'draft' && (
                  <button
                    type="button"
                    onClick={() => void handleSubmit(order.id)}
                  >
                    Submit
                  </button>
                )}
              </div>

              {expandedId === order.id && (
                <div className="order-detail">
                  {detailLoading && <p>Loading detail...</p>}
                  {!detailLoading && detail && (
                    <>
                      <h4>Lines</h4>
                      {detail.lines.length === 0 ? (
                        <p className="empty">No lines.</p>
                      ) : (
                        <ul>
                          {detail.lines.map((line) => (
                            <li key={line.id}>
                              Catalog #{line.catalog_item_id} x{line.quantity}{' '}
                              @ {line.unit_price}
                            </li>
                          ))}
                        </ul>
                      )}
                      <h4>Address</h4>
                      {detail.address ? (
                        <p>
                          {detail.address.street}, {detail.address.city}{' '}
                          {detail.address.zip_code} | {detail.address.phone}
                          {detail.address.notes && ` — ${detail.address.notes}`}
                        </p>
                      ) : (
                        <p className="empty">No address set.</p>
                      )}
                      {detail.feedback && (
                        <>
                          <h4>Feedback</h4>
                          <p>{detail.feedback}</p>
                        </>
                      )}
                    </>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
