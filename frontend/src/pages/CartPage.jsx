import { Link } from 'react-router-dom';
import { ShoppingBag, Trash2, Plus, Minus } from 'lucide-react';
import { useCart } from '../context/CartContext';
import styles from './CartPage.module.css';

function getPlaceholderColor(id) {
  const colors = ['#FFE082','#B2DFDB','#BBDEFB','#F8BBD0','#C8E6C9','#E1BEE7','#FFCCBC','#CFD8DC'];
  const index = id ? id.charCodeAt(id.length - 1) % colors.length : 0;
  return colors[index];
}

export default function CartPage() {
  const { items, removeFromCart, updateQuantity, clearCart, totalPrice } = useCart();

  const vat = totalPrice * 0.05;
  const total = totalPrice + vat;
  const savings = items.reduce((sum, i) => {
    return sum + (i.product.originalPrice - i.product.price) * i.quantity;
  }, 0);

  if (items.length === 0) {
    return (
      <div className={styles.empty}>
        <ShoppingBag size={80} color="var(--noon-border)" />
        <h2>Your cart is empty</h2>
        <p>Add items to start shopping</p>
        <Link to="/" className={styles.shopBtn}>Continue Shopping</Link>
      </div>
    );
  }

  return (
    <div className="container">
      <div className={styles.header}>
        <h1 className={styles.pageTitle}>My Cart ({items.length} {items.length === 1 ? 'item' : 'items'})</h1>
        <button className={styles.clearBtn} onClick={clearCart}>Clear All</button>
      </div>

      <div className={styles.layout}>
        <div className={styles.itemsList}>
          {items.map(item => {
            const { product, quantity } = item;
            const color = getPlaceholderColor(product.id);
            return (
              <div key={product.id} className={styles.cartItem}>
                <div className={styles.itemImage} style={{ background: color }}>
                  <span className={styles.itemInitials}>{product.brand.slice(0, 2).toUpperCase()}</span>
                </div>
                <div className={styles.itemDetails}>
                  <Link to={`/product/${product.id}`} className={styles.itemBrand}>{product.brand}</Link>
                  <Link to={`/product/${product.id}`} className={styles.itemTitle}>{product.title}</Link>
                  {product.expressDelivery && (
                    <span className={styles.expressTag}>Express Delivery Available</span>
                  )}
                  <div className={styles.itemFooter}>
                    <div className={styles.qtyControls}>
                      <button
                        className={styles.qtyBtn}
                        onClick={() => updateQuantity(product.id, quantity - 1)}
                      >
                        <Minus size={12} />
                      </button>
                      <span className={styles.qtyNum}>{quantity}</span>
                      <button
                        className={styles.qtyBtn}
                        onClick={() => updateQuantity(product.id, quantity + 1)}
                      >
                        <Plus size={12} />
                      </button>
                    </div>
                    <div className={styles.itemPrices}>
                      <span className={styles.itemPrice}>AED {(product.price * quantity).toLocaleString()}</span>
                      {product.originalPrice > product.price && (
                        <span className={styles.itemOriginalPrice}>
                          AED {(product.originalPrice * quantity).toLocaleString()}
                        </span>
                      )}
                    </div>
                    <button
                      className={styles.removeBtn}
                      onClick={() => removeFromCart(product.id)}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className={styles.summary}>
          <h2 className={styles.summaryTitle}>Order Summary</h2>
          <div className={styles.summaryRows}>
            <div className={styles.summaryRow}>
              <span>Subtotal ({items.reduce((s, i) => s + i.quantity, 0)} items)</span>
              <span>AED {totalPrice.toLocaleString()}</span>
            </div>
            {savings > 0 && (
              <div className={`${styles.summaryRow} ${styles.savingsRow}`}>
                <span>Your savings</span>
                <span>- AED {savings.toLocaleString()}</span>
              </div>
            )}
            <div className={styles.summaryRow}>
              <span>Delivery</span>
              <span className={styles.freeDelivery}>FREE</span>
            </div>
            <div className={styles.summaryRow}>
              <span>VAT (5%)</span>
              <span>AED {vat.toFixed(2)}</span>
            </div>
          </div>
          <div className={styles.totalRow}>
            <span>Total</span>
            <span>AED {total.toFixed(2)}</span>
          </div>
          <button className={styles.checkoutBtn}>
            Proceed to Checkout
          </button>
          <Link to="/" className={styles.continueLink}>Continue Shopping</Link>
        </div>
      </div>
    </div>
  );
}
