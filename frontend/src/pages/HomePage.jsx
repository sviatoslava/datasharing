import HeroBanner from '../components/home/HeroBanner';
import CategoryGrid from '../components/home/CategoryGrid';
import FeaturedSection from '../components/home/FeaturedSection';
import styles from './HomePage.module.css';

export default function HomePage() {
  return (
    <div>
      <HeroBanner />
      <CategoryGrid />
      <FeaturedSection title="Featured Products" queryParams={{ tags: 'featured', limit: 10 }} />

      <div className={styles.promoBanner}>
        <div className="container">
          <div className={styles.promoGrid}>
            <div className={styles.promoCard} style={{ background: '#1A1A1A' }}>
              <span className={styles.promoTag}>EXPRESS</span>
              <h3>Same Day Delivery</h3>
              <p>Order before 2PM for same-day delivery</p>
            </div>
            <div className={styles.promoCard} style={{ background: '#F5CF00', color: '#1A1A1A' }}>
              <span className={styles.promoTag} style={{ background: '#1A1A1A', color: '#F5CF00' }}>DEALS</span>
              <h3>Top Deals Today</h3>
              <p>Save up to 50% on selected items</p>
            </div>
            <div className={styles.promoCard} style={{ background: '#27AE60' }}>
              <span className={styles.promoTag} style={{ background: 'rgba(255,255,255,0.2)', color: 'white' }}>VERIFIED</span>
              <h3>100% Authentic</h3>
              <p>All products are genuine and verified</p>
            </div>
          </div>
        </div>
      </div>

      <FeaturedSection title="Electronics Deals" queryParams={{ category: 'electronics', sort: 'discount_desc', limit: 10 }} />
      <FeaturedSection title="Fashion Picks" queryParams={{ category: 'fashion', limit: 10 }} />
      <FeaturedSection title="Top Rated" queryParams={{ sort: 'rating_desc', limit: 10 }} />
      <FeaturedSection title="Best Sellers" queryParams={{ tags: 'bestseller', limit: 10 }} />
    </div>
  );
}
