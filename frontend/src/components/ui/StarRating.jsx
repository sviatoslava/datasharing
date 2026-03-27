import { Star } from 'lucide-react';

export default function StarRating({ rating, reviewCount, size = 14 }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      {[1, 2, 3, 4, 5].map(i => (
        <Star
          key={i}
          size={size}
          fill={i <= Math.round(rating) ? 'var(--noon-yellow)' : 'none'}
          color={i <= Math.round(rating) ? 'var(--noon-yellow)' : '#ccc'}
        />
      ))}
      {reviewCount !== undefined && (
        <span style={{ fontSize: 12, color: 'var(--noon-text-light)', marginLeft: 4 }}>
          ({reviewCount.toLocaleString()})
        </span>
      )}
    </div>
  );
}
