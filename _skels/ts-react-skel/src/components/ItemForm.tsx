/**
 * `ItemForm` — controlled form that creates a new item via the
 * `useItems` hook. Receives the hook from the parent so multiple
 * components can share a single cache.
 */

import { useCallback, useState, type FormEvent, type ReactElement } from 'react';

import { AuthError, type Item, type NewItem } from '../api/items';
import { type Category, type NewCategory } from '../api/categories';

export interface ItemFormProps {
  create: (payload: NewItem) => Promise<Item>;
  onCreated?: (item: Item) => void;
  categories?: Category[];
  createCategory?: (payload: NewCategory) => Promise<Category | null>;
}

export default function ItemForm({ create, onCreated, categories = [] }: ItemFormProps): ReactElement {
  const [name, setName] = useState<string>('');
  const [description, setDescription] = useState<string>('');
  const [categoryId, setCategoryId] = useState<number | null>(null);
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
          category_id: categoryId,
        });
        setName('');
        setDescription('');
        setCategoryId(null);
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
    [name, description, categoryId, create, onCreated]
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

      <label>
        Category
        <select
          name="category_id"
          value={categoryId ?? ''}
          onChange={(event) => setCategoryId(event.target.value ? Number(event.target.value) : null)}
        >
          <option value="">No category</option>
          {categories.map((cat) => (
            <option key={cat.id} value={cat.id}>
              {cat.name}
            </option>
          ))}
        </select>
      </label>

      <button type="submit" disabled={submitting || name.trim().length === 0}>
        {submitting ? 'Saving…' : 'Create item'}
      </button>

      {error && <p className="error">{error}</p>}
    </form>
  );
}
