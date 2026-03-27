import { Trash2, Plus, Minus } from 'lucide-react';
import { useCart } from '../../context/CartContext';
import styles from './CartItem.module.css';

function getPlaceholderColor(id) {
  const colors = ['#FFE082','#B2DFDB','#BBDEFB','#F8BBD0','#C8E6C9','#E1BEE7','#FFCCBC','#CFD8DC'];
  const index = id ? id.charCodeAt(id.length - 1) % colors.length : 0;
  return colors[index];
}

export default function CartItem({ item }) {
  const { removeFromCart, updateQuantity } = useCart();
  const { product, quantity } = item;

  return (
    <div className={styles.item}>
      <div className={styles.image} style={{ background: getPlaceholderColor(product.id) }}>
        <span className={styles.initials}>{product.brand.slice(0, 2).toUpperCase()}</span>
      </div>
      <div className={styles.details}>
        <p className={styles.brand}>{product.brand}</p>
        <p className={styles.title}>{product.title}</p>
        <p className={styles.price}>AED {product.price.toLocaleString()}</p>
        <div className={styles.actions}>
          <div className={styles.qty}>
            <button
              className={styles.qtyBtn}
              onClick={() => updateQuantity(product.id, quantity - 1)}
              aria-label="Decrease"
            >
              <Minus size={12} />
            </button>
            <span className={styles.qtyNum}>{quantity}</span>
            <button
              className={styles.qtyBtn}
              onClick={() => updateQuantity(product.id, quantity + 1)}
              aria-label="Increase"
            >
              <Plus size={12} />
            </button>
          </div>
          <button
            className={styles.removeBtn}
            onClick={() => removeFromCart(product.id)}
            aria-label="Remove item"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
