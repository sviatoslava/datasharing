import { Link } from 'react-router-dom';
import { ShoppingCart, Zap } from 'lucide-react';
import { useCart } from '../../context/CartContext';
import StarRating from '../ui/StarRating';
import toast from 'react-hot-toast';
import styles from './ProductCard.module.css';

// Deterministic placeholder color based on product id
function getPlaceholderColor(id) {
  const colors = ['#FFE082','#B2DFDB','#BBDEFB','#F8BBD0','#C8E6C9','#E1BEE7','#FFCCBC','#CFD8DC'];
  const index = id ? id.charCodeAt(id.length - 1) % colors.length : 0;
  return colors[index];
}

export default function ProductCard({ product }) {
  const { addToCart, isInCart } = useCart();

  const handleAddToCart = (e) => {
    e.preventDefault();
    e.stopPropagation();
    addToCart(product);
    toast.success(`${product.title.slice(0, 30)}... added to cart`);
  };

  const inCart = isInCart(product.id);
  const placeholderColor = getPlaceholderColor(product.id);

  return (
    <Link to={`/product/${product.id}`} className={styles.card}>
      <div className={styles.imageWrapper} style={{ background: placeholderColor }}>
        {product.discount > 0 && (
          <span className={styles.discountBadge}>{product.discount}% OFF</span>
        )}
        {product.expressDelivery && (
          <span className={styles.expressBadge}>
            <Zap size={10} /> Express
          </span>
        )}
        <div className={styles.imagePlaceholder}>
          <span className={styles.productInitials}>
            {product.brand.slice(0, 2).toUpperCase()}
          </span>
        </div>
      </div>

      <div className={styles.info}>
        <p className={styles.brand}>{product.brand}</p>
        <h3 className={styles.title}>{product.title}</h3>
        <StarRating rating={product.rating} reviewCount={product.reviewCount} />

        <div className={styles.priceRow}>
          <span className={styles.price}>AED {product.price.toLocaleString()}</span>
          {product.originalPrice > product.price && (
            <span className={styles.originalPrice}>AED {product.originalPrice.toLocaleString()}</span>
          )}
        </div>

        {product.expressDelivery && (
          <p className={styles.delivery}>Express delivery available</p>
        )}

        <button
          className={`${styles.addToCartBtn} ${inCart ? styles.inCart : ''}`}
          onClick={handleAddToCart}
        >
          <ShoppingCart size={14} />
          {inCart ? 'In Cart' : 'Add to Cart'}
        </button>
      </div>
    </Link>
  );
}
