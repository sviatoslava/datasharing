import { Link } from 'react-router-dom';
import { X, ShoppingBag } from 'lucide-react';
import { useCart } from '../../context/CartContext';
import CartItem from './CartItem';
import styles from './CartDrawer.module.css';

export default function CartDrawer() {
  const { items, isDrawerOpen, closeDrawer, totalPrice } = useCart();

  return (
    <>
      {isDrawerOpen && (
        <div className={styles.overlay} onClick={closeDrawer} />
      )}
      <div className={`${styles.drawer} ${isDrawerOpen ? styles.open : ''}`}>
        <div className={styles.header}>
          <h2 className={styles.title}>My Cart ({items.length})</h2>
          <button className={styles.closeBtn} onClick={closeDrawer} aria-label="Close cart">
            <X size={20} />
          </button>
        </div>

        <div className={styles.body}>
          {items.length === 0 ? (
            <div className={styles.empty}>
              <ShoppingBag size={48} color="var(--noon-border)" />
              <p>Your cart is empty</p>
              <button className={styles.shopBtn} onClick={closeDrawer}>
                <Link to="/">Continue Shopping</Link>
              </button>
            </div>
          ) : (
            items.map(item => <CartItem key={item.product.id} item={item} />)
          )}
        </div>

        {items.length > 0 && (
          <div className={styles.footer}>
            <div className={styles.total}>
              <span>Subtotal</span>
              <span className={styles.totalAmount}>AED {totalPrice.toLocaleString()}</span>
            </div>
            <Link to="/cart" className={styles.checkoutBtn} onClick={closeDrawer}>
              View Cart & Checkout
            </Link>
          </div>
        )}
      </div>
    </>
  );
}
