import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Laptop, Shirt, Home, Sparkles, Dumbbell, Gamepad2, BookOpen, ShoppingBasket } from 'lucide-react';
import { fetchCategories } from '../../api/client';
import styles from './CategoryGrid.module.css';

const ICONS = { Laptop, Shirt, Home, Sparkles, Dumbbell, Gamepad2, BookOpen, ShoppingBasket };

export default function CategoryGrid() {
  const { data, isLoading } = useQuery({ queryKey: ['categories'], queryFn: fetchCategories });

  if (isLoading) return <div className={styles.placeholder} />;

  const categories = data?.categories || [];

  return (
    <section className={styles.section}>
      <div className="container">
        <h2 className={styles.heading}>Shop by Category</h2>
        <div className={styles.grid}>
          {categories.map(cat => {
            const Icon = ICONS[cat.icon] || ShoppingBasket;
            return (
              <Link key={cat.id} to={`/products?category=${cat.id}`} className={styles.card}>
                <div className={styles.iconWrapper} style={{ background: cat.color + '22', borderColor: cat.color + '44' }}>
                  <Icon size={28} color={cat.color} />
                </div>
                <span className={styles.label}>{cat.label}</span>
                <span className={styles.count}>{cat.productCount} items</span>
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}
