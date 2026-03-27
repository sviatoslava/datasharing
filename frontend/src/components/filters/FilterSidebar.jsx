import { useSearchParams } from 'react-router-dom';
import styles from './FilterSidebar.module.css';

const CATEGORIES = [
  { id: '', label: 'All Categories' },
  { id: 'electronics', label: 'Electronics' },
  { id: 'fashion', label: 'Fashion' },
  { id: 'home-kitchen', label: 'Home & Kitchen' },
  { id: 'beauty', label: 'Beauty' },
  { id: 'sports', label: 'Sports' },
  { id: 'toys', label: 'Toys' },
  { id: 'books', label: 'Books' },
  { id: 'grocery', label: 'Grocery' },
];

const RATINGS = [
  { value: '4', label: '4 stars & above' },
  { value: '3', label: '3 stars & above' },
  { value: '2', label: '2 stars & above' },
];

export default function FilterSidebar({ onClose }) {
  const [params, setParams] = useSearchParams();

  const set = (key, value) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    next.delete('page');
    setParams(next);
  };

  const clearAll = () => {
    const next = new URLSearchParams();
    setParams(next);
  };

  const category = params.get('category') || '';
  const minPrice = params.get('minPrice') || '';
  const maxPrice = params.get('maxPrice') || '';
  const minRating = params.get('minRating') || '';
  const expressOnly = params.get('express') || '';

  const hasFilters = category || minPrice || maxPrice || minRating || expressOnly;

  return (
    <aside className={styles.sidebar}>
      <div className={styles.header}>
        <h3>Filters</h3>
        <div className={styles.headerActions}>
          {hasFilters && (
            <button className={styles.clearBtn} onClick={clearAll}>Clear All</button>
          )}
          {onClose && (
            <button className={styles.closeBtn} onClick={onClose}>✕</button>
          )}
        </div>
      </div>

      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>Category</h4>
        {CATEGORIES.map(cat => (
          <label key={cat.id} className={styles.option}>
            <input
              type="radio"
              name="category"
              checked={category === cat.id}
              onChange={() => set('category', cat.id)}
            />
            <span>{cat.label}</span>
          </label>
        ))}
      </div>

      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>Price Range (AED)</h4>
        <div className={styles.priceInputs}>
          <input
            type="number"
            placeholder="Min"
            value={minPrice}
            onChange={e => set('minPrice', e.target.value)}
            className={styles.priceInput}
            min="0"
          />
          <span>–</span>
          <input
            type="number"
            placeholder="Max"
            value={maxPrice}
            onChange={e => set('maxPrice', e.target.value)}
            className={styles.priceInput}
            min="0"
          />
        </div>
      </div>

      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>Customer Rating</h4>
        <label className={styles.option}>
          <input
            type="radio"
            name="rating"
            checked={minRating === ''}
            onChange={() => set('minRating', '')}
          />
          <span>All ratings</span>
        </label>
        {RATINGS.map(r => (
          <label key={r.value} className={styles.option}>
            <input
              type="radio"
              name="rating"
              checked={minRating === r.value}
              onChange={() => set('minRating', r.value)}
            />
            <span>{r.label}</span>
          </label>
        ))}
      </div>

      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>Delivery</h4>
        <label className={styles.option}>
          <input
            type="checkbox"
            checked={expressOnly === '1'}
            onChange={e => set('express', e.target.checked ? '1' : '')}
          />
          <span>Express delivery</span>
        </label>
      </div>
    </aside>
  );
}
