import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Search } from 'lucide-react';
import { searchProducts } from '../api/client';
import ProductGrid from '../components/product/ProductGrid';
import FilterSidebar from '../components/filters/FilterSidebar';
import styles from './SearchResultsPage.module.css';

const SORT_OPTIONS = [
  { value: '', label: 'Relevance' },
  { value: 'price_asc', label: 'Price: Low to High' },
  { value: 'price_desc', label: 'Price: High to Low' },
  { value: 'rating_desc', label: 'Top Rated' },
];

export default function SearchResultsPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') || '';
  const sort = params.get('sort') || '';
  const category = params.get('category') || '';
  const minPrice = params.get('minPrice') || '';
  const maxPrice = params.get('maxPrice') || '';
  const page = parseInt(params.get('page') || '1');

  const { data, isLoading } = useQuery({
    queryKey: ['search', q, category, sort, minPrice, maxPrice, page],
    queryFn: () => searchProducts({ q, sort, category, minPrice, maxPrice, page, limit: 20 }),
    enabled: !!q,
  });

  const products = data?.products || [];
  const total = data?.total || 0;
  const totalPages = data?.totalPages || 1;

  const setSort = (value) => {
    const next = new URLSearchParams(params);
    if (value) next.set('sort', value);
    else next.delete('sort');
    setParams(next);
  };

  const setPage = (p) => {
    const next = new URLSearchParams(params);
    next.set('page', p);
    setParams(next);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="container">
      <div className={styles.searchHeader}>
        <Search size={20} color="var(--noon-text-light)" />
        <h1 className={styles.searchTitle}>
          {q ? (
            <>Search results for <em>"{q}"</em></>
          ) : (
            'Search products'
          )}
        </h1>
        {!isLoading && q && (
          <span className={styles.count}>({total} results)</span>
        )}
      </div>

      <div className={styles.layout}>
        <div className={styles.sidebarDesktop}>
          <FilterSidebar />
        </div>

        <div className={styles.main}>
          <div className={styles.toolbar}>
            <span className={styles.resultCount}>
              {isLoading ? 'Searching...' : `${total} products found`}
            </span>
            <div className={styles.sortWrapper}>
              <label className={styles.sortLabel}>Sort:</label>
              <select
                className={styles.sortSelect}
                value={sort}
                onChange={e => setSort(e.target.value)}
              >
                {SORT_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
          </div>

          {!q ? (
            <div className={styles.noQuery}>
              <Search size={64} color="var(--noon-border)" />
              <p>Enter a search term to find products</p>
            </div>
          ) : (
            <ProductGrid products={products} loading={isLoading} />
          )}

          {totalPages > 1 && (
            <div className={styles.pagination}>
              {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
                <button
                  key={p}
                  className={`${styles.pageBtn} ${p === page ? styles.pageBtnActive : ''}`}
                  onClick={() => setPage(p)}
                >
                  {p}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
