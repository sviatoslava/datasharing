const express = require('express');
const router = express.Router();
const products = require('../data/products');

router.get('/', (req, res) => {
  const { q = '', category, sort, minPrice, maxPrice, page = 1, limit = 20 } = req.query;
  const query = q.toLowerCase().trim();

  let result = products.filter(p =>
    p.title.toLowerCase().includes(query) ||
    p.brand.toLowerCase().includes(query) ||
    p.description.toLowerCase().includes(query) ||
    p.tags.some(t => t.toLowerCase().includes(query)) ||
    p.category.toLowerCase().includes(query) ||
    p.subcategory.toLowerCase().includes(query)
  );

  if (category) result = result.filter(p => p.category === category);
  if (minPrice) result = result.filter(p => p.price >= parseFloat(minPrice));
  if (maxPrice) result = result.filter(p => p.price <= parseFloat(maxPrice));
  if (sort === 'price_asc') result.sort((a, b) => a.price - b.price);
  else if (sort === 'price_desc') result.sort((a, b) => b.price - a.price);
  else if (sort === 'rating_desc') result.sort((a, b) => b.rating - a.rating);

  const total = result.length;
  const totalPages = Math.ceil(total / parseInt(limit));
  const start = (parseInt(page) - 1) * parseInt(limit);
  const paginated = result.slice(start, start + parseInt(limit));

  res.json({ products: paginated, total, page: parseInt(page), totalPages, query: q });
});

module.exports = router;
