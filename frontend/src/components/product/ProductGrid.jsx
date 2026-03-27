import ProductCard from './ProductCard';
import styles from './ProductGrid.module.css';

export default function ProductGrid({ products, loading }) {
  if (loading) {
    return (
      <div className={styles.grid}>
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className={styles.skeleton} />
        ))}
      </div>
    );
  }

  if (!products || products.length === 0) {
    return (
      <div className={styles.empty}>
        <p>No products found</p>
      </div>
    );
  }

  return (
    <div className={styles.grid}>
      {products.map(p => <ProductCard key={p.id} product={p} />)}
    </div>
  );
}
