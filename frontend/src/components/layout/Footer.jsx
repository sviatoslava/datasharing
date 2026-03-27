import { Link } from 'react-router-dom';
import styles from './Footer.module.css';

export default function Footer() {
  return (
    <footer className={styles.footer}>
      <div className="container">
        <div className={styles.grid}>
          <div>
            <div className={styles.logo}>noon</div>
            <p className={styles.tagline}>Your online shopping destination</p>
            <p className={styles.desc}>Shop millions of products from top brands with fast delivery across UAE, Saudi Arabia, and Egypt.</p>
          </div>
          <div>
            <h4>Shop</h4>
            <ul>
              <li><Link to="/products?category=electronics">Electronics</Link></li>
              <li><Link to="/products?category=fashion">Fashion</Link></li>
              <li><Link to="/products?category=home-kitchen">Home & Kitchen</Link></li>
              <li><Link to="/products?category=beauty">Beauty</Link></li>
            </ul>
          </div>
          <div>
            <h4>Account</h4>
            <ul>
              <li><a href="#">Sign In</a></li>
              <li><a href="#">Register</a></li>
              <li><Link to="/cart">My Cart</Link></li>
              <li><a href="#">My Orders</a></li>
            </ul>
          </div>
          <div>
            <h4>Help</h4>
            <ul>
              <li><a href="#">Customer Service</a></li>
              <li><a href="#">Returns Policy</a></li>
              <li><a href="#">Track Order</a></li>
              <li><a href="#">Delivery Info</a></li>
            </ul>
          </div>
        </div>
        <div className={styles.bottom}>
          <p>&copy; 2024 Noon - All rights reserved</p>
          <div className={styles.bottomLinks}>
            <a href="#">Privacy Policy</a>
            <a href="#">Terms of Use</a>
            <a href="#">Cookie Policy</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
