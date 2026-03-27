const express = require('express');
const router = express.Router();
const products = require('../data/products');

router.get('/', (req, res) => {
  let result = [...products];
  const { category, minPrice, maxPrice, minRating, brand, sort, page = 1, limit = 20, tags } = req.query;

  if (category) result = result.filter(p => p.category === category);
  if (minPrice) result = result.filter(p => p.price >= parseFloat(minPrice));
  if (maxPrice) result = result.filter(p => p.price <= parseFloat(maxPrice));
  if (minRating) result = result.filter(p => p.rating >= parseFloat(minRating));
  if (brand) result = result.filter(p => p.brand.toLowerCase() === brand.toLowerCase());
  if (tags) result = result.filter(p => p.tags.includes(tags));

  if (sort === 'price_asc') result.sort((a, b) => a.price - b.price);
  else if (sort === 'price_desc') result.sort((a, b) => b.price - a.price);
  else if (sort === 'rating_desc') result.sort((a, b) => b.rating - a.rating);
  else if (sort === 'discount_desc') result.sort((a, b) => b.discount - a.discount);

  const total = result.length;
  const totalPages = Math.ceil(total / parseInt(limit));
  const start = (parseInt(page) - 1) * parseInt(limit);
  const paginated = result.slice(start, start + parseInt(limit));

  res.json({ products: paginated, total, page: parseInt(page), totalPages });
});

router.get('/featured', (req, res) => {
  const featured = products.filter(p => p.tags.includes('featured')).slice(0, 12);
  res.json({ products: featured });
});

router.get('/:id', (req, res) => {
  const product = products.find(p => p.id === req.params.id || p.slug === req.params.id);
  if (!product) return res.status(404).json({ error: 'Product not found' });
  const related = products.filter(p => p.category === product.category && p.id !== product.id).slice(0, 8);
  res.json({ product, related });
});

module.exports = router;
