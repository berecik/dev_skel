/**
 * `ItemForm` — controlled form that creates a new item via the
 * `useItems` hook. Receives the hook from the parent so multiple
 * components can share a single cache.
 */

import { useCallback, useState, type FormEvent, type ReactElement } from 'react';

import { AuthError, type Item, type NewItem } from '../api/items';

export interface ItemFormProps {
  create: (payload: NewItem) => Promise<Item>;
  onCreated?: (item: Item) => void;
}

export default function ItemForm({ create, onCreated }: ItemFormProps): ReactElement {
  const [name, setName] = useState<string>('');
  const [description, setDescription] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>): Promise<void> => {
      event.preventDefault();
      setSubmitting(true);
      setError(null);
      try {
        const created = await create({
          name,
          description: description || null,
        });
        setName('');
        setDescription('');
        onCreated?.(created);
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
    [name, description, create, onCreated]
  );

  return (
    <form className="item-form" onSubmit={handleSubmit}>
      <h2>New item</h2>

      <label>
        Name
        <input
          type="text"
          name="name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
        />
      </label>

      <label>
        Description
        <textarea
          name="description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={2}
        />
      </label>

      <button type="submit" disabled={submitting || name.trim().length === 0}>
        {submitting ? 'Saving…' : 'Create item'}
      </button>

      {error && <p className="error">{error}</p>}
    </form>
  );
}
