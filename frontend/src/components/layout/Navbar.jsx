import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ShoppingCart, Search, Menu, X } from 'lucide-react';
import { useCart } from '../../context/CartContext';
import CartDrawer from '../cart/CartDrawer';
import styles from './Navbar.module.css';

const CATEGORIES = [
  { id: 'electronics', label: 'Electronics' },
  { id: 'fashion', label: 'Fashion' },
  { id: 'home-kitchen', label: 'Home & Kitchen' },
  { id: 'beauty', label: 'Beauty' },
  { id: 'sports', label: 'Sports' },
  { id: 'toys', label: 'Toys' },
  { id: 'books', label: 'Books' },
  { id: 'grocery', label: 'Grocery' },
];

export default function Navbar() {
  const [query, setQuery] = useState('');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { totalItems, openDrawer } = useCart();
  const navigate = useNavigate();

  const handleSearch = (e) => {
    e.preventDefault();
    if (query.trim()) {
      navigate(`/search?q=${encodeURIComponent(query.trim())}`);
    }
  };

  return (
    <>
      <nav className={styles.navbar}>
        {/* Top bar */}
        <div className={styles.topBar}>
          <div className="container">
            <span>Free delivery on orders over AED 100</span>
            <span>UAE | AED</span>
          </div>
        </div>

        {/* Main bar */}
        <div className={styles.mainBar}>
          <div className={`container ${styles.mainBarInner}`}>
            <Link to="/" className={styles.logo}>
              <span className={styles.logoText}>noon</span>
            </Link>

            <form className={styles.searchForm} onSubmit={handleSearch}>
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Search for products, brands and more..."
                className={styles.searchInput}
              />
              <button type="submit" className={styles.searchBtn} aria-label="Search">
                <Search size={20} />
              </button>
            </form>

            <div className={styles.actions}>
              <button
                className={styles.cartBtn}
                onClick={openDrawer}
                aria-label="Open cart"
              >
                <ShoppingCart size={22} />
                {totalItems > 0 && (
                  <span className={styles.cartBadge}>{totalItems}</span>
                )}
                <span className={styles.cartLabel}>Cart</span>
              </button>

              <button
                className={styles.mobileMenuBtn}
                onClick={() => setMobileMenuOpen(v => !v)}
                aria-label="Menu"
              >
                {mobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
              </button>
            </div>
          </div>
        </div>

        {/* Category bar */}
        <div className={styles.categoryBar}>
          <div className={`container ${styles.categoryBarInner}`}>
            {CATEGORIES.map(cat => (
              <Link
                key={cat.id}
                to={`/products?category=${cat.id}`}
                className={styles.catLink}
              >
                {cat.label}
              </Link>
            ))}
          </div>
        </div>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <div className={styles.mobileMenu}>
            <form onSubmit={handleSearch} className={styles.mobileSearchForm}>
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Search..."
                className={styles.searchInput}
              />
              <button type="submit" className={styles.searchBtn}>
                <Search size={18} />
              </button>
            </form>
            {CATEGORIES.map(cat => (
              <Link
                key={cat.id}
                to={`/products?category=${cat.id}`}
                className={styles.mobileCatLink}
                onClick={() => setMobileMenuOpen(false)}
              >
                {cat.label}
              </Link>
            ))}
          </div>
        )}
      </nav>
      <CartDrawer />
    </>
  );
}
