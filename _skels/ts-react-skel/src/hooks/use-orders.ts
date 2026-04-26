/**
 * `useOrders` — custom React hook that wraps the typed order workflow.
 *
 * Same pattern as `useItems`: re-fetches when the bearer token changes,
 * provides mutation callbacks, and surfaces `unauthorized` so the UI
 * can prompt for login.
 *
 *     const {
 *       orders, loading, error, unauthorized,
 *       refresh, createOrder, getOrderDetail,
 *       addLine, submitOrder, approveOrder, rejectOrder,
 *     } = useOrders();
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import {
  type ApproveBody,
  type NewOrderLine,
  type Order,
  type OrderDetail,
  type RejectBody,
  addOrderLine,
  approveOrder as approveOrderRequest,
  createOrder as createOrderRequest,
  getOrder,
  listOrders as listOrdersRequest,
  rejectOrder as rejectOrderRequest,
  submitOrder as submitOrderRequest,
} from '../api/orders';
import { AuthError } from '../api/auth';
import { useAuthToken } from '../auth/use-auth-token';

export interface UseOrdersResult {
  orders: Order[];
  loading: boolean;
  error: string | null;
  /**
   * `true` when the most recent error was a 401 from the backend —
   * lets the UI render a re-login prompt without sniffing strings.
   */
  unauthorized: boolean;
  /** Re-fetch the list explicitly (e.g. after a manual refresh button). */
  refresh: () => Promise<void>;
  /** Create a new draft order and prepend it into the local cache. */
  createOrder: () => Promise<Order>;
  /** Fetch full order detail (lines + address). */
  getOrderDetail: (id: number) => Promise<OrderDetail>;
  /** Add a line to an order. */
  addLine: (orderId: number, payload: NewOrderLine) => Promise<void>;
  /** Submit a draft order. */
  submitOrder: (orderId: number) => Promise<void>;
  /** Approve a submitted order. */
  approveOrder: (orderId: number, payload: ApproveBody) => Promise<void>;
  /** Reject a submitted order. */
  rejectOrder: (orderId: number, payload: RejectBody) => Promise<void>;
}

export function useOrders(): UseOrdersResult {
  const { token, clearToken } = useAuthToken();

  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [unauthorized, setUnauthorized] = useState<boolean>(false);

  // Capture the freshest token in a ref so mutation callbacks always
  // send the right Authorization header even when they were memoised
  // before the latest login.
  const tokenRef = useRef<string | null>(token);
  useEffect(() => {
    tokenRef.current = token;
  }, [token]);

  // Effect-driven list fetch — re-runs whenever the token changes
  // (login or logout). Abort the in-flight request when the token
  // changes again (or the component unmounts).
  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    async function load(): Promise<void> {
      setLoading(true);
      setError(null);
      setUnauthorized(false);
      try {
        const data = await listOrdersRequest({
          token,
          signal: controller.signal,
        });
        if (!cancelled) {
          setOrders(data);
        }
      } catch (err) {
        if (cancelled || (err instanceof DOMException && err.name === 'AbortError')) {
          return;
        }
        if (err instanceof AuthError) {
          setUnauthorized(true);
          clearToken();
          return;
        }
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [token, clearToken]);

  const refresh = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError(null);
    setUnauthorized(false);
    try {
      const data = await listOrdersRequest({ token: tokenRef.current });
      setOrders(data);
    } catch (err) {
      if (err instanceof AuthError) {
        setUnauthorized(true);
        clearToken();
        return;
      }
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [clearToken]);

  const create = useCallback(async (): Promise<Order> => {
    const created = await createOrderRequest({
      token: tokenRef.current,
    });
    setOrders((prev) => [created, ...prev]);
    return created;
  }, []);

  const getOrderDetail = useCallback(
    async (id: number): Promise<OrderDetail> => {
      return getOrder(id, { token: tokenRef.current });
    },
    [],
  );

  const addLine = useCallback(
    async (orderId: number, payload: NewOrderLine): Promise<void> => {
      await addOrderLine(orderId, payload, { token: tokenRef.current });
    },
    [],
  );

  const submit = useCallback(
    async (orderId: number): Promise<void> => {
      const updated = await submitOrderRequest(orderId, {
        token: tokenRef.current,
      });
      setOrders((prev) =>
        prev.map((o) => (o.id === orderId ? updated : o)),
      );
    },
    [],
  );

  const approve = useCallback(
    async (orderId: number, payload: ApproveBody): Promise<void> => {
      const updated = await approveOrderRequest(orderId, payload, {
        token: tokenRef.current,
      });
      setOrders((prev) =>
        prev.map((o) => (o.id === orderId ? updated : o)),
      );
    },
    [],
  );

  const reject = useCallback(
    async (orderId: number, payload: RejectBody): Promise<void> => {
      const updated = await rejectOrderRequest(orderId, payload, {
        token: tokenRef.current,
      });
      setOrders((prev) =>
        prev.map((o) => (o.id === orderId ? updated : o)),
      );
    },
    [],
  );

  return {
    orders,
    loading,
    error,
    unauthorized,
    refresh,
    createOrder: create,
    getOrderDetail,
    addLine,
    submitOrder: submit,
    approveOrder: approve,
    rejectOrder: reject,
  };
}
