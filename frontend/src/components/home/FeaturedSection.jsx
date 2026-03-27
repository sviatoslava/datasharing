import { useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { fetchProducts } from '../../api/client';
import ProductCard from '../product/ProductCard';
import styles from './FeaturedSection.module.css';

export default function FeaturedSection({ title, queryParams = {} }) {
  const scrollRef = useRef(null);
  const { data, isLoading } = useQuery({
    queryKey: ['products', queryParams],
    queryFn: () => fetchProducts({ ...queryParams, limit: 10 }),
  });

  const scroll = (dir) => {
    if (scrollRef.current) {
      scrollRef.current.scrollBy({ left: dir * 280, behavior: 'smooth' });
    }
  };

  const products = data?.products || [];

  return (
    <section className={styles.section}>
      <div className="container">
        <div className={styles.header}>
          <h2 className={styles.title}>{title}</h2>
          <div className={styles.arrows}>
            <button className={styles.arrow} onClick={() => scroll(-1)} aria-label="Scroll left">
              <ChevronLeft size={18} />
            </button>
            <button className={styles.arrow} onClick={() => scroll(1)} aria-label="Scroll right">
              <ChevronRight size={18} />
            </button>
          </div>
        </div>

        <div className={styles.scrollContainer} ref={scrollRef}>
          {isLoading
            ? Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className={styles.skeleton} />
              ))
            : products.map(p => (
                <div key={p.id} className={styles.cardWrapper}>
                  <ProductCard product={p} />
                </div>
              ))
          }
        </div>
      </div>
    </section>
  );
}
