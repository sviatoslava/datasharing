import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ShoppingCart, Minus, Plus, Star, Zap, CheckCircle } from 'lucide-react';
import { fetchProductById } from '../api/client';
import { useCart } from '../context/CartContext';
import StarRating from '../components/ui/StarRating';
import FeaturedSection from '../components/home/FeaturedSection';
import toast from 'react-hot-toast';
import styles from './ProductDetailPage.module.css';

function getPlaceholderColor(id) {
  const colors = ['#FFE082','#B2DFDB','#BBDEFB','#F8BBD0','#C8E6C9','#E1BEE7','#FFCCBC','#CFD8DC'];
  const index = id ? id.charCodeAt(id.length - 1) % colors.length : 0;
  return colors[index];
}

export default function ProductDetailPage() {
  const { id } = useParams();
  const [quantity, setQuantity] = useState(1);
  const { addToCart } = useCart();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['product', id],
    queryFn: () => fetchProductById(id),
  });

  if (isLoading) return (
    <div className="container" style={{ textAlign: 'center', padding: '80px 0' }}>
      <div className="spinner" style={{ margin: '0 auto' }} />
    </div>
  );

  if (isError || !data?.product) return (
    <div className="container" style={{ textAlign: 'center', padding: '80px 0' }}>
      <p>Product not found.</p>
      <Link to="/products" style={{ color: 'var(--noon-blue)' }}>Back to products</Link>
    </div>
  );

  const { product } = data;
  const color = getPlaceholderColor(product.id);

  const handleAddToCart = () => {
    for (let i = 0; i < quantity; i++) addToCart(product);
    toast.success(`${quantity}x ${product.title.slice(0, 25)}... added to cart`);
  };

  return (
    <div>
      <div className="container">
        {/* Breadcrumb */}
        <div className={styles.breadcrumb}>
          <Link to="/">Home</Link> /&nbsp;
          <Link to={`/products?category=${product.category}`}>
            {product.category.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())}
          </Link> /&nbsp;
          <span>{product.title}</span>
        </div>

        <div className={styles.layout}>
          {/* Product image */}
          <div className={styles.imageSection}>
            <div className={styles.mainImage} style={{ background: color }}>
              <div className={styles.imagePlaceholder}>
                <span className={styles.brandBig}>{product.brand.slice(0, 3).toUpperCase()}</span>
              </div>
              {product.discount > 0 && (
                <span className={styles.discountBadge}>{product.discount}% OFF</span>
              )}
              {product.expressDelivery && (
                <span className={styles.expressBadge}><Zap size={12} /> Express</span>
              )}
            </div>
            <div className={styles.thumbnails}>
              {[1, 2, 3, 4].map(i => (
                <div key={i} className={styles.thumb} style={{ background: color, opacity: i === 1 ? 1 : 0.5 }}>
                  <span style={{ fontSize: 14, fontWeight: 900, color: 'rgba(0,0,0,0.2)' }}>
                    {product.brand.slice(0, 2).toUpperCase()}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Product info */}
          <div className={styles.infoSection}>
            <p className={styles.brand}>{product.brand}</p>
            <h1 className={styles.title}>{product.title}</h1>

            <div className={styles.ratingRow}>
              <StarRating rating={product.rating} reviewCount={product.reviewCount} size={16} />
              <span className={styles.ratingNum}>{product.rating}/5</span>
            </div>

            <div className={styles.priceSection}>
              <div className={styles.priceRow}>
                <span className={styles.price}>AED {product.price.toLocaleString()}</span>
                {product.originalPrice > product.price && (
                  <span className={styles.originalPrice}>AED {product.originalPrice.toLocaleString()}</span>
                )}
                {product.discount > 0 && (
                  <span className={styles.saveBadge}>Save {product.discount}%</span>
                )}
              </div>
              <p className={styles.vatNote}>VAT included</p>
            </div>

            <div className={styles.deliveryInfo}>
              <div className={styles.deliveryRow}>
                <CheckCircle size={16} color="var(--noon-green)" />
                {product.expressDelivery
                  ? <span className={styles.expressText}>Express delivery tomorrow</span>
                  : <span>Delivery in {product.deliveryDays} days</span>
                }
              </div>
              <div className={styles.deliveryRow}>
                <CheckCircle size={16} color="var(--noon-green)" />
                <span>Sold by <strong>{product.soldBy}</strong></span>
              </div>
              <div className={styles.deliveryRow}>
                <CheckCircle size={16} color="var(--noon-green)" />
                <span>{product.inStock ? `In Stock (${product.stockCount} available)` : 'Out of Stock'}</span>
              </div>
            </div>

            <div className={styles.qtySection}>
              <span className={styles.qtyLabel}>Quantity:</span>
              <div className={styles.qtyControls}>
                <button
                  className={styles.qtyBtn}
                  onClick={() => setQuantity(q => Math.max(1, q - 1))}
                  disabled={quantity <= 1}
                >
                  <Minus size={14} />
                </button>
                <span className={styles.qtyNum}>{quantity}</span>
                <button
                  className={styles.qtyBtn}
                  onClick={() => setQuantity(q => q + 1)}
                  disabled={quantity >= product.stockCount}
                >
                  <Plus size={14} />
                </button>
              </div>
            </div>

            <button
              className={styles.addToCartBtn}
              onClick={handleAddToCart}
              disabled={!product.inStock}
            >
              <ShoppingCart size={18} />
              Add to Cart
            </button>

            <p className={styles.description}>{product.description}</p>

            {product.specs && Object.keys(product.specs).length > 0 && (
              <div className={styles.specs}>
                <h3 className={styles.specsTitle}>Specifications</h3>
                <table className={styles.specsTable}>
                  <tbody>
                    {Object.entries(product.specs).map(([key, val]) => (
                      <tr key={key}>
                        <td className={styles.specKey}>{key}</td>
                        <td className={styles.specVal}>{val}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      <FeaturedSection
        title="You May Also Like"
        queryParams={{ category: product.category, limit: 10 }}
      />
    </div>
  );
}
