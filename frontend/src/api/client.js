import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 8000,
});

export const fetchProducts = (params) => api.get('/products', { params }).then(r => r.data);
export const fetchFeaturedProducts = () => api.get('/products/featured').then(r => r.data);
export const fetchProductById = (id) => api.get(`/products/${id}`).then(r => r.data);
export const fetchCategories = () => api.get('/categories').then(r => r.data);
export const fetchBanners = () => api.get('/banners').then(r => r.data);
export const searchProducts = (params) => api.get('/search', { params }).then(r => r.data);

export default api;
