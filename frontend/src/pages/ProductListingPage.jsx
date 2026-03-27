import { useState } from 'react';
import { useSearchParams, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { SlidersHorizontal, X } from 'lucide-react';
import { fetchProducts } from '../api/client';
import ProductGrid from '../components/product/ProductGrid';
import FilterSidebar from '../components/filters/FilterSidebar';
import styles from './ProductListingPage.module.css';

const SORT_OPTIONS = [
  { value: '', label: 'Relevance' },
  { value: 'price_asc', label: 'Price: Low to High' },
  { value: 'price_desc', label: 'Price: High to Low' },
  { value: 'rating_desc', label: 'Top Rated' },
  { value: 'discount_desc', label: 'Biggest Discount' },
];

export default function ProductListingPage() {
  const [params, setParams] = useSearchParams();
  const [showMobileFilter, setShowMobileFilter] = useState(false);

  const category = params.get('category') || '';
  const sort = params.get('sort') || '';
  const minPrice = params.get('minPrice') || '';
  const maxPrice = params.get('maxPrice') || '';
  const minRating = params.get('minRating') || '';
  const page = parseInt(params.get('page') || '1');

  const queryParams = { category, sort, minPrice, maxPrice, minRating, page, limit: 20 };

  const { data, isLoading } = useQuery({
    queryKey: ['products', queryParams],
    queryFn: () => fetchProducts(queryParams),
  });

  const products = data?.products || [];
  const total = data?.total || 0;
  const totalPages = data?.totalPages || 1;

  const setSort = (value) => {
    const next = new URLSearchParams(params);
    if (value) next.set('sort', value);
    else next.delete('sort');
    next.delete('page');
    setParams(next);
  };

  const setPage = (p) => {
    const next = new URLSearchParams(params);
    next.set('page', p);
    setParams(next);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const categoryLabel = category
    ? category.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())
    : 'All Products';

  return (
    <div className="container">
      <div className={styles.breadcrumb}>
        <a href="/">Home</a> / <span>{categoryLabel}</span>
      </div>

      <div className={styles.layout}>
        {/* Desktop sidebar */}
        <div className={styles.sidebarDesktop}>
          <FilterSidebar />
        </div>

        {/* Mobile filter overlay */}
        {showMobileFilter && (
          <div className={styles.mobileFilterOverlay}>
            <div className={styles.mobileFilterPanel}>
              <FilterSidebar onClose={() => setShowMobileFilter(false)} />
            </div>
          </div>
        )}

        <div className={styles.main}>
          <div className={styles.toolbar}>
            <div className={styles.toolbarLeft}>
              <button
                className={styles.filterToggle}
                onClick={() => setShowMobileFilter(true)}
              >
                <SlidersHorizontal size={16} /> Filters
              </button>
              <span className={styles.resultCount}>
                {isLoading ? '...' : `${total} results`}
                {category && ` in ${categoryLabel}`}
              </span>
            </div>
            <div className={styles.sortWrapper}>
              <label className={styles.sortLabel}>Sort by:</label>
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

          <ProductGrid products={products} loading={isLoading} />

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
