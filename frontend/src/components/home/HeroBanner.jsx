import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchBanners } from '../../api/client';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import styles from './HeroBanner.module.css';

export default function HeroBanner() {
  const { data } = useQuery({ queryKey: ['banners'], queryFn: fetchBanners });
  const [current, setCurrent] = useState(0);
  const banners = data?.banners || [];

  useEffect(() => {
    if (banners.length <= 1) return;
    const timer = setInterval(() => setCurrent(c => (c + 1) % banners.length), 4000);
    return () => clearInterval(timer);
  }, [banners.length]);

  if (banners.length === 0) return <div className={styles.placeholder} />;

  const banner = banners[current];

  return (
    <div className={styles.wrapper} style={{ background: banner.bgColor }}>
      <div className={`container ${styles.content}`}>
        <div className={styles.text} style={{ color: banner.textColor }}>
          {banner.tag && (
            <span className={styles.tag} style={{ background: banner.accentColor, color: banner.bgColor }}>
              {banner.tag}
            </span>
          )}
          <h1 className={styles.title}>{banner.title}</h1>
          <p className={styles.subtitle}>{banner.subtitle}</p>
          <Link
            to={banner.ctaLink}
            className={styles.cta}
            style={{ background: banner.accentColor, color: banner.bgColor }}
          >
            {banner.cta}
          </Link>
        </div>
        <div className={styles.illustration}>
          <div className={styles.shapeCircle} style={{ background: banner.accentColor, opacity: 0.15 }} />
          <span className={styles.bigText} style={{ color: banner.accentColor, opacity: 0.1 }}>
            {banner.title.split(' ')[0]}
          </span>
        </div>
      </div>

      {banners.length > 1 && (
        <>
          <button
            className={`${styles.navBtn} ${styles.navLeft}`}
            onClick={() => setCurrent(c => (c - 1 + banners.length) % banners.length)}
            aria-label="Previous"
          >
            <ChevronLeft size={20} />
          </button>
          <button
            className={`${styles.navBtn} ${styles.navRight}`}
            onClick={() => setCurrent(c => (c + 1) % banners.length)}
            aria-label="Next"
          >
            <ChevronRight size={20} />
          </button>
          <div className={styles.dots}>
            {banners.map((_, i) => (
              <button
                key={i}
                className={`${styles.dot} ${i === current ? styles.dotActive : ''}`}
                onClick={() => setCurrent(i)}
                aria-label={`Slide ${i + 1}`}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
