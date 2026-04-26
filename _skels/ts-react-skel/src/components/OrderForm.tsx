/**
 * `OrderForm` — form to create an order, add catalog items as lines,
 * set a delivery address, and submit.
 *
 * Keeps it simple: the user picks from a catalog dropdown, specifies
 * quantity, and can add multiple lines before submitting the order.
 */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactElement,
} from 'react';

import {
  type CatalogItem,
  type NewOrderAddress,
  type NewOrderLine,
  type Order,
  listCatalog,
} from '../api/orders';
import { AuthError } from '../api/auth';
import { useAuthToken } from '../auth/use-auth-token';

export interface OrderFormProps {
  createOrder: () => Promise<Order>;
  addLine: (orderId: number, payload: NewOrderLine) => Promise<void>;
  setAddress: (orderId: number, payload: NewOrderAddress) => Promise<void>;
  submitOrder: (orderId: number) => Promise<void>;
  onOrderCreated?: () => void;
}

interface PendingLine {
  catalog_item_id: number;
  quantity: number;
  label: string;
}

export default function OrderForm({
  createOrder,
  addLine,
  setAddress,
  submitOrder,
  onOrderCreated,
}: OrderFormProps): ReactElement {
  const { token } = useAuthToken();
  const tokenRef = useRef<string | null>(token);
  useEffect(() => {
    tokenRef.current = token;
  }, [token]);

  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [catalogItemId, setCatalogItemId] = useState<number | ''>('');
  const [quantity, setQuantity] = useState<number>(1);
  const [lines, setLines] = useState<PendingLine[]>([]);

  // Address fields
  const [street, setStreet] = useState('');
  const [city, setCity] = useState('');
  const [zipCode, setZipCode] = useState('');
  const [phone, setPhone] = useState('');
  const [notes, setNotes] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load catalog on mount / token change
  useEffect(() => {
    const controller = new AbortController();
    listCatalog({ token: tokenRef.current, signal: controller.signal })
      .then((items) => setCatalog(items))
      .catch(() => {
        // Catalog load failure is non-fatal — the form still renders.
      });
    return () => controller.abort();
  }, [token]);

  const handleAddLine = useCallback(() => {
    if (catalogItemId === '') return;
    const item = catalog.find((c) => c.id === catalogItemId);
    setLines((prev) => [
      ...prev,
      {
        catalog_item_id: catalogItemId,
        quantity,
        label: item ? item.name : `#${catalogItemId}`,
      },
    ]);
    setCatalogItemId('');
    setQuantity(1);
  }, [catalogItemId, quantity, catalog]);

  const handleRemoveLine = useCallback((index: number) => {
    setLines((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>): Promise<void> => {
      event.preventDefault();
      if (lines.length === 0) return;
      setSubmitting(true);
      setError(null);
      try {
        // 1. Create draft order
        const order = await createOrder();

        // 2. Add all lines
        for (const line of lines) {
          await addLine(order.id, {
            catalog_item_id: line.catalog_item_id,
            quantity: line.quantity,
          });
        }

        // 3. Set address (if street is provided)
        if (street.trim()) {
          await setAddress(order.id, {
            street,
            city,
            zip_code: zipCode,
            phone,
            notes: notes || undefined,
          });
        }

        // 4. Submit
        await submitOrder(order.id);

        // Reset form
        setLines([]);
        setStreet('');
        setCity('');
        setZipCode('');
        setPhone('');
        setNotes('');
        onOrderCreated?.();
      } catch (err) {
        if (err instanceof AuthError) {
          setError('Your session expired — please sign in again.');
        } else {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        setSubmitting(false);
      }
    },
    [lines, street, city, zipCode, phone, notes, createOrder, addLine, setAddress, submitOrder, onOrderCreated],
  );

  return (
    <form className="order-form" onSubmit={handleSubmit}>
      <h2>New order</h2>

      {/* ── Line builder ─────────────────────────────────────────── */}
      <fieldset>
        <legend>Order lines</legend>
        <div className="line-builder">
          <label>
            Catalog item
            <select
              value={catalogItemId}
              onChange={(e) =>
                setCatalogItemId(e.target.value ? Number(e.target.value) : '')
              }
            >
              <option value="">Select item...</option>
              {catalog
                .filter((c) => c.available)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.price})
                  </option>
                ))}
            </select>
          </label>
          <label>
            Qty
            <input
              type="number"
              min={1}
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
            />
          </label>
          <button
            type="button"
            onClick={handleAddLine}
            disabled={catalogItemId === ''}
          >
            Add line
          </button>
        </div>
        {lines.length > 0 && (
          <ul className="pending-lines">
            {lines.map((line, idx) => (
              <li key={idx}>
                {line.label} x{line.quantity}
                <button type="button" onClick={() => handleRemoveLine(idx)}>
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </fieldset>

      {/* ── Address ──────────────────────────────────────────────── */}
      <fieldset>
        <legend>Delivery address</legend>
        <label>
          Street
          <input
            type="text"
            value={street}
            onChange={(e) => setStreet(e.target.value)}
          />
        </label>
        <label>
          City
          <input
            type="text"
            value={city}
            onChange={(e) => setCity(e.target.value)}
          />
        </label>
        <label>
          ZIP code
          <input
            type="text"
            value={zipCode}
            onChange={(e) => setZipCode(e.target.value)}
          />
        </label>
        <label>
          Phone
          <input
            type="text"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </label>
        <label>
          Notes
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
          />
        </label>
      </fieldset>

      <button
        type="submit"
        disabled={submitting || lines.length === 0}
      >
        {submitting ? 'Placing order...' : 'Place order'}
      </button>

      {error && <p className="error">{error}</p>}
    </form>
  );
}
