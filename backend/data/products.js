const products = [
  // Electronics - Smartphones
  {
    id: "p001", title: "Samsung Galaxy S24 Ultra", slug: "samsung-galaxy-s24-ultra",
    category: "electronics", subcategory: "smartphones", price: 3999, originalPrice: 4599,
    discount: 13, currency: "AED", rating: 4.8, reviewCount: 2341, brand: "Samsung",
    inStock: true, stockCount: 45, tags: ["featured", "bestseller"],
    description: "Experience the ultimate Galaxy with the S24 Ultra featuring 200MP camera, titanium frame, and AI-powered features.",
    specs: { RAM: "12GB", Storage: "256GB", Display: "6.8 inch Dynamic AMOLED", Battery: "5000mAh" },
    deliveryDays: 1, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p002", title: "Apple iPhone 15 Pro Max", slug: "apple-iphone-15-pro-max",
    category: "electronics", subcategory: "smartphones", price: 5499, originalPrice: 5999,
    discount: 8, currency: "AED", rating: 4.9, reviewCount: 3102, brand: "Apple",
    inStock: true, stockCount: 30, tags: ["featured", "bestseller"],
    description: "iPhone 15 Pro Max with A17 Pro chip, titanium design, and advanced camera system.",
    specs: { RAM: "8GB", Storage: "256GB", Display: "6.7 inch Super Retina XDR", Battery: "4422mAh" },
    deliveryDays: 1, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p003", title: "Google Pixel 8 Pro", slug: "google-pixel-8-pro",
    category: "electronics", subcategory: "smartphones", price: 3299, originalPrice: 3799,
    discount: 13, currency: "AED", rating: 4.6, reviewCount: 876, brand: "Google",
    inStock: true, stockCount: 20, tags: ["featured"],
    description: "Google's most advanced phone with Tensor G3 chip and 7 years of OS updates.",
    specs: { RAM: "12GB", Storage: "128GB", Display: "6.7 inch LTPO OLED", Battery: "5050mAh" },
    deliveryDays: 2, soldBy: "Noon", expressDelivery: false
  },
  {
    id: "p004", title: "OnePlus 12 5G", slug: "oneplus-12-5g",
    category: "electronics", subcategory: "smartphones", price: 2799, originalPrice: 3199,
    discount: 13, currency: "AED", rating: 4.5, reviewCount: 654, brand: "OnePlus",
    inStock: true, stockCount: 35, tags: [],
    description: "Flagship killer with Snapdragon 8 Gen 3 and 100W SUPERVOOC charging.",
    specs: { RAM: "12GB", Storage: "256GB", Display: "6.82 inch LTPO AMOLED", Battery: "5400mAh" },
    deliveryDays: 2, soldBy: "Seller", expressDelivery: false
  },
  // Electronics - Laptops
  {
    id: "p005", title: "MacBook Pro 14-inch M3", slug: "macbook-pro-14-m3",
    category: "electronics", subcategory: "laptops", price: 7999, originalPrice: 8999,
    discount: 11, currency: "AED", rating: 4.9, reviewCount: 1432, brand: "Apple",
    inStock: true, stockCount: 15, tags: ["featured", "bestseller"],
    description: "MacBook Pro with M3 chip delivers incredible performance in a compact design.",
    specs: { RAM: "18GB", Storage: "512GB SSD", Display: "14.2 inch Liquid Retina XDR", Battery: "Up to 18 hours" },
    deliveryDays: 1, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p006", title: "Dell XPS 15 OLED", slug: "dell-xps-15-oled",
    category: "electronics", subcategory: "laptops", price: 6499, originalPrice: 7299,
    discount: 11, currency: "AED", rating: 4.7, reviewCount: 892, brand: "Dell",
    inStock: true, stockCount: 12, tags: ["featured"],
    description: "Premium Windows laptop with stunning OLED display and Intel Core i9 processor.",
    specs: { RAM: "32GB", Storage: "1TB SSD", Display: "15.6 inch OLED 3.5K", Battery: "Up to 13 hours" },
    deliveryDays: 2, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p007", title: "HP Spectre x360 14", slug: "hp-spectre-x360-14",
    category: "electronics", subcategory: "laptops", price: 5299, originalPrice: 5999,
    discount: 12, currency: "AED", rating: 4.6, reviewCount: 543, brand: "HP",
    inStock: true, stockCount: 8, tags: [],
    description: "2-in-1 convertible laptop with Intel Core Ultra 7 and OLED touch display.",
    specs: { RAM: "16GB", Storage: "512GB SSD", Display: "14 inch OLED 2.8K", Battery: "Up to 17 hours" },
    deliveryDays: 3, soldBy: "Seller", expressDelivery: false
  },
  // Electronics - Audio
  {
    id: "p008", title: "Sony WH-1000XM5 Headphones", slug: "sony-wh-1000xm5",
    category: "electronics", subcategory: "audio", price: 1299, originalPrice: 1599,
    discount: 19, currency: "AED", rating: 4.8, reviewCount: 2876, brand: "Sony",
    inStock: true, stockCount: 60, tags: ["featured", "bestseller"],
    description: "Industry-leading noise cancellation with 30-hour battery life.",
    specs: { Type: "Over-ear", "Noise Cancellation": "Yes", Battery: "30 hours", Connectivity: "Bluetooth 5.2" },
    deliveryDays: 1, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p009", title: "Apple AirPods Pro 2nd Gen", slug: "apple-airpods-pro-2nd-gen",
    category: "electronics", subcategory: "audio", price: 899, originalPrice: 1099,
    discount: 18, currency: "AED", rating: 4.7, reviewCount: 3421, brand: "Apple",
    inStock: true, stockCount: 80, tags: ["featured", "bestseller"],
    description: "AirPods Pro with Adaptive Audio and USB-C charging case.",
    specs: { Type: "In-ear", "Noise Cancellation": "Active", Battery: "6+30 hours", Connectivity: "Bluetooth 5.3" },
    deliveryDays: 1, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p010", title: "JBL Charge 5 Speaker", slug: "jbl-charge-5-speaker",
    category: "electronics", subcategory: "audio", price: 599, originalPrice: 699,
    discount: 14, currency: "AED", rating: 4.6, reviewCount: 1243, brand: "JBL",
    inStock: true, stockCount: 45, tags: [],
    description: "Portable Bluetooth speaker with 20-hour battery and power bank feature.",
    specs: { Type: "Portable", Waterproof: "IP67", Battery: "20 hours", Connectivity: "Bluetooth 5.1" },
    deliveryDays: 2, soldBy: "Noon", expressDelivery: true
  },
  // Fashion - Men
  {
    id: "p011", title: "Nike Air Max 270 Sneakers", slug: "nike-air-max-270",
    category: "fashion", subcategory: "mens-shoes", price: 649, originalPrice: 799,
    discount: 19, currency: "AED", rating: 4.5, reviewCount: 1876, brand: "Nike",
    inStock: true, stockCount: 50, tags: ["featured", "bestseller"],
    description: "Lifestyle sneakers with the largest Air unit in heel for all-day comfort.",
    specs: { Material: "Mesh & Synthetic", Sole: "Rubber", "Care": "Spot clean" },
    deliveryDays: 2, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p012", title: "Adidas Ultraboost 23", slug: "adidas-ultraboost-23",
    category: "fashion", subcategory: "mens-shoes", price: 749, originalPrice: 899,
    discount: 17, currency: "AED", rating: 4.7, reviewCount: 1432, brand: "Adidas",
    inStock: true, stockCount: 35, tags: ["featured"],
    description: "Performance running shoes with BOOST midsole for energy return.",
    specs: { Material: "Primeknit", Sole: "Continental Rubber", Type: "Running" },
    deliveryDays: 2, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p013", title: "Levi's 511 Slim Jeans", slug: "levis-511-slim-jeans",
    category: "fashion", subcategory: "mens-clothing", price: 299, originalPrice: 399,
    discount: 25, currency: "AED", rating: 4.4, reviewCount: 987, brand: "Levi's",
    inStock: true, stockCount: 100, tags: ["bestseller"],
    description: "Classic slim fit jeans with stretch for comfort and style.",
    specs: { Material: "99% Cotton, 1% Elastane", Fit: "Slim", Rise: "Mid-rise" },
    deliveryDays: 3, soldBy: "Seller", expressDelivery: false
  },
  {
    id: "p014", title: "Tommy Hilfiger Polo Shirt", slug: "tommy-hilfiger-polo",
    category: "fashion", subcategory: "mens-clothing", price: 249, originalPrice: 349,
    discount: 29, currency: "AED", rating: 4.5, reviewCount: 654, brand: "Tommy Hilfiger",
    inStock: true, stockCount: 75, tags: [],
    description: "Classic polo shirt in premium pique cotton with iconic logo.",
    specs: { Material: "100% Cotton Pique", Fit: "Regular", Sleeve: "Short" },
    deliveryDays: 2, soldBy: "Noon", expressDelivery: true
  },
  // Fashion - Women
  {
    id: "p015", title: "Zara Floral Midi Dress", slug: "zara-floral-midi-dress",
    category: "fashion", subcategory: "womens-clothing", price: 189, originalPrice: 269,
    discount: 30, currency: "AED", rating: 4.3, reviewCount: 432, brand: "Zara",
    inStock: true, stockCount: 60, tags: ["featured"],
    description: "Elegant floral print midi dress perfect for any occasion.",
    specs: { Material: "100% Viscose", Length: "Midi", Pattern: "Floral" },
    deliveryDays: 3, soldBy: "Seller", expressDelivery: false
  },
  {
    id: "p016", title: "Michael Kors Leather Handbag", slug: "michael-kors-leather-handbag",
    category: "fashion", subcategory: "bags", price: 999, originalPrice: 1399,
    discount: 29, currency: "AED", rating: 4.6, reviewCount: 876, brand: "Michael Kors",
    inStock: true, stockCount: 25, tags: ["featured", "bestseller"],
    description: "Luxury leather handbag with gold-tone hardware and multiple compartments.",
    specs: { Material: "Genuine Leather", Closure: "Zipper", Strap: "Adjustable" },
    deliveryDays: 2, soldBy: "Noon", expressDelivery: true
  },
  // Home & Kitchen
  {
    id: "p017", title: "Dyson V15 Detect Vacuum", slug: "dyson-v15-detect-vacuum",
    category: "home-kitchen", subcategory: "cleaning", price: 2499, originalPrice: 2999,
    discount: 17, currency: "AED", rating: 4.8, reviewCount: 1543, brand: "Dyson",
    inStock: true, stockCount: 20, tags: ["featured", "bestseller"],
    description: "Cordless vacuum with laser dust detection and 60-minute battery.",
    specs: { Type: "Cordless", Battery: "60 minutes", Filtration: "HEPA", Weight: "3.1 kg" },
    deliveryDays: 1, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p018", title: "Nespresso Vertuo Next Coffee Machine", slug: "nespresso-vertuo-next",
    category: "home-kitchen", subcategory: "kitchen-appliances", price: 699, originalPrice: 899,
    discount: 22, currency: "AED", rating: 4.7, reviewCount: 2134, brand: "Nespresso",
    inStock: true, stockCount: 40, tags: ["featured"],
    description: "Smart coffee machine brewing 5 cup sizes with Bluetooth connectivity.",
    specs: { "Cup Sizes": "5", Connectivity: "Bluetooth", "Tank Capacity": "1.5L" },
    deliveryDays: 2, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p019", title: "Instant Pot Duo 7-in-1", slug: "instant-pot-duo-7-in-1",
    category: "home-kitchen", subcategory: "kitchen-appliances", price: 499, originalPrice: 649,
    discount: 23, currency: "AED", rating: 4.6, reviewCount: 3421, brand: "Instant Pot",
    inStock: true, stockCount: 55, tags: ["bestseller"],
    description: "Electric pressure cooker, slow cooker, rice cooker and more in one.",
    specs: { Capacity: "5.7L", Functions: "7", Material: "Stainless Steel" },
    deliveryDays: 2, soldBy: "Noon", expressDelivery: false
  },
  {
    id: "p020", title: "IKEA KALLAX Shelf Unit", slug: "ikea-kallax-shelf",
    category: "home-kitchen", subcategory: "furniture", price: 349, originalPrice: 399,
    discount: 13, currency: "AED", rating: 4.4, reviewCount: 876, brand: "IKEA",
    inStock: true, stockCount: 30, tags: [],
    description: "Versatile shelf unit perfect for storage and display.",
    specs: { Material: "Particleboard", Dimensions: "77x77 cm", Color: "White" },
    deliveryDays: 3, soldBy: "Seller", expressDelivery: false
  },
  // Beauty
  {
    id: "p021", title: "La Mer Crème de la Mer Moisturizer", slug: "la-mer-creme-moisturizer",
    category: "beauty", subcategory: "skincare", price: 799, originalPrice: 949,
    discount: 16, currency: "AED", rating: 4.7, reviewCount: 1243, brand: "La Mer",
    inStock: true, stockCount: 25, tags: ["featured", "bestseller"],
    description: "Iconic moisturizer with Miracle Broth for transformative hydration.",
    specs: { Size: "30ml", "Skin Type": "All", SPF: "None" },
    deliveryDays: 2, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p022", title: "Charlotte Tilbury Flawless Filter", slug: "charlotte-tilbury-flawless-filter",
    category: "beauty", subcategory: "makeup", price: 179, originalPrice: 219,
    discount: 18, currency: "AED", rating: 4.6, reviewCount: 987, brand: "Charlotte Tilbury",
    inStock: true, stockCount: 60, tags: ["featured"],
    description: "Complexion booster for luminous, filtered skin.",
    specs: { Finish: "Luminous", Coverage: "Light", "Size": "30ml" },
    deliveryDays: 2, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p023", title: "Dyson Airwrap Complete Styler", slug: "dyson-airwrap-complete",
    category: "beauty", subcategory: "hair-care", price: 2199, originalPrice: 2499,
    discount: 12, currency: "AED", rating: 4.8, reviewCount: 2341, brand: "Dyson",
    inStock: true, stockCount: 15, tags: ["featured", "bestseller"],
    description: "Multi-styler for curling, waving, and smoothing with no extreme heat.",
    specs: { Attachments: "6", Technology: "Coanda effect", Voltage: "220-240V" },
    deliveryDays: 1, soldBy: "Noon", expressDelivery: true
  },
  // Sports
  {
    id: "p024", title: "Garmin Fenix 7X Pro Smartwatch", slug: "garmin-fenix-7x-pro",
    category: "sports", subcategory: "smartwatches", price: 3999, originalPrice: 4499,
    discount: 11, currency: "AED", rating: 4.7, reviewCount: 876, brand: "Garmin",
    inStock: true, stockCount: 12, tags: ["featured"],
    description: "Premium multisport GPS watch with solar charging and advanced metrics.",
    specs: { Battery: "28 days", GPS: "Multi-band", Display: "1.4 inch MIP", Waterproof: "10 ATM" },
    deliveryDays: 2, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p025", title: "Peloton Bike+", slug: "peloton-bike-plus",
    category: "sports", subcategory: "fitness-equipment", price: 8999, originalPrice: 9999,
    discount: 10, currency: "AED", rating: 4.6, reviewCount: 543, brand: "Peloton",
    inStock: true, stockCount: 5, tags: ["featured"],
    description: "Premium connected fitness bike with rotating 23.8 inch HD touchscreen.",
    specs: { Display: "23.8 inch", Resistance: "Magnetic", "Max Weight": "136 kg" },
    deliveryDays: 5, soldBy: "Noon", expressDelivery: false
  },
  {
    id: "p026", title: "Wilson Pro Staff RF97 Tennis Racket", slug: "wilson-pro-staff-rf97",
    category: "sports", subcategory: "racket-sports", price: 899, originalPrice: 1099,
    discount: 18, currency: "AED", rating: 4.5, reviewCount: 432, brand: "Wilson",
    inStock: true, stockCount: 20, tags: [],
    description: "Roger Federer's signature racket with precision and control.",
    specs: { Weight: "340g", "Head Size": "97 sq in", "String Pattern": "16x19" },
    deliveryDays: 3, soldBy: "Seller", expressDelivery: false
  },
  // Toys
  {
    id: "p027", title: "LEGO Technic Lamborghini Sián", slug: "lego-technic-lamborghini",
    category: "toys", subcategory: "building-sets", price: 1499, originalPrice: 1799,
    discount: 17, currency: "AED", rating: 4.9, reviewCount: 1543, brand: "LEGO",
    inStock: true, stockCount: 18, tags: ["featured", "bestseller"],
    description: "3,696-piece replica of the Lamborghini Sián FKP 37 supercar.",
    specs: { Pieces: "3696", Age: "18+", Scale: "1:8" },
    deliveryDays: 2, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p028", title: "Barbie Dreamhouse", slug: "barbie-dreamhouse",
    category: "toys", subcategory: "dolls", price: 699, originalPrice: 849,
    discount: 18, currency: "AED", rating: 4.6, reviewCount: 876, brand: "Mattel",
    inStock: true, stockCount: 25, tags: ["featured"],
    description: "3-story dream house with slide, pool, and 75+ accessories.",
    specs: { Floors: "3", Rooms: "8", Accessories: "75+" },
    deliveryDays: 2, soldBy: "Noon", expressDelivery: false
  },
  // Books
  {
    id: "p029", title: "Atomic Habits by James Clear", slug: "atomic-habits",
    category: "books", subcategory: "self-help", price: 69, originalPrice: 89,
    discount: 22, currency: "AED", rating: 4.8, reviewCount: 5432, brand: "Penguin",
    inStock: true, stockCount: 200, tags: ["featured", "bestseller"],
    description: "Tiny changes, remarkable results. The #1 New York Times bestseller.",
    specs: { Pages: "320", Language: "English", Format: "Paperback" },
    deliveryDays: 1, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p030", title: "The Psychology of Money", slug: "psychology-of-money",
    category: "books", subcategory: "finance", price: 59, originalPrice: 79,
    discount: 25, currency: "AED", rating: 4.7, reviewCount: 3214, brand: "Harriman House",
    inStock: true, stockCount: 150, tags: ["bestseller"],
    description: "Timeless lessons on wealth, greed, and happiness.",
    specs: { Pages: "256", Language: "English", Format: "Paperback" },
    deliveryDays: 1, soldBy: "Noon", expressDelivery: true
  },
  // Grocery
  {
    id: "p031", title: "Al Ain Water 500ml x 24", slug: "al-ain-water-24-pack",
    category: "grocery", subcategory: "beverages", price: 29, originalPrice: 35,
    discount: 17, currency: "AED", rating: 4.5, reviewCount: 2341, brand: "Al Ain",
    inStock: true, stockCount: 500, tags: ["bestseller"],
    description: "Pure natural spring water from the mountains of Al Ain.",
    specs: { Volume: "500ml x 24", Type: "Spring Water", Flavor: "Natural" },
    deliveryDays: 1, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p032", title: "Nescafe Gold Blend 200g", slug: "nescafe-gold-200g",
    category: "grocery", subcategory: "beverages", price: 45, originalPrice: 55,
    discount: 18, currency: "AED", rating: 4.4, reviewCount: 1876, brand: "Nescafe",
    inStock: true, stockCount: 300, tags: [],
    description: "Premium instant coffee blend for a smooth, rich taste.",
    specs: { Weight: "200g", Type: "Instant Coffee", Caffeine: "Medium" },
    deliveryDays: 1, soldBy: "Noon", expressDelivery: true
  },
  // More Electronics
  {
    id: "p033", title: "iPad Pro 12.9 inch M2", slug: "ipad-pro-12-9-m2",
    category: "electronics", subcategory: "tablets", price: 4999, originalPrice: 5599,
    discount: 11, currency: "AED", rating: 4.8, reviewCount: 1654, brand: "Apple",
    inStock: true, stockCount: 22, tags: ["featured"],
    description: "iPad Pro with M2 chip, Liquid Retina XDR display, and Thunderbolt port.",
    specs: { RAM: "8GB", Storage: "256GB", Display: "12.9 inch Liquid Retina XDR", Connectivity: "Wi-Fi 6E" },
    deliveryDays: 1, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p034", title: "Samsung 65\" QLED 4K Smart TV", slug: "samsung-65-qled-4k",
    category: "electronics", subcategory: "tvs", price: 3799, originalPrice: 4499,
    discount: 16, currency: "AED", rating: 4.7, reviewCount: 987, brand: "Samsung",
    inStock: true, stockCount: 10, tags: ["featured", "bestseller"],
    description: "Quantum Dot technology for brilliant 4K picture quality.",
    specs: { Size: "65 inch", Resolution: "4K UHD", HDR: "Quantum HDR", SmartTV: "Tizen OS" },
    deliveryDays: 3, soldBy: "Noon", expressDelivery: false
  },
  {
    id: "p035", title: "Sony PlayStation 5 Console", slug: "sony-ps5-console",
    category: "electronics", subcategory: "gaming", price: 1999, originalPrice: 2199,
    discount: 9, currency: "AED", rating: 4.9, reviewCount: 4321, brand: "Sony",
    inStock: true, stockCount: 8, tags: ["featured", "bestseller"],
    description: "Next-gen gaming with ultra-high speed SSD, Tempest 3D AudioTech.",
    specs: { CPU: "AMD Zen 2 3.5GHz", GPU: "10.3 TFLOPS", Storage: "825GB SSD", "Optical Drive": "4K Blu-ray" },
    deliveryDays: 1, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p036", title: "Canon EOS R6 Mark II Camera", slug: "canon-eos-r6-mark-ii",
    category: "electronics", subcategory: "cameras", price: 11999, originalPrice: 13499,
    discount: 11, currency: "AED", rating: 4.8, reviewCount: 654, brand: "Canon",
    inStock: true, stockCount: 6, tags: ["featured"],
    description: "Full-frame mirrorless camera with 40fps burst shooting and 4K60p video.",
    specs: { Sensor: "20.1MP Full-frame", ISO: "100-102400", Video: "4K60p", Stabilization: "5-axis IBIS" },
    deliveryDays: 2, soldBy: "Noon", expressDelivery: true
  },
  // More Fashion
  {
    id: "p037", title: "Ray-Ban Aviator Classic Sunglasses", slug: "ray-ban-aviator-classic",
    category: "fashion", subcategory: "accessories", price: 699, originalPrice: 849,
    discount: 18, currency: "AED", rating: 4.7, reviewCount: 2134, brand: "Ray-Ban",
    inStock: true, stockCount: 40, tags: ["bestseller"],
    description: "Iconic aviator sunglasses with crystal green lenses.",
    specs: { Frame: "Metal", Lens: "Crystal", UV: "100% UV Protection" },
    deliveryDays: 2, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p038", title: "Rolex Datejust 41 Watch", slug: "rolex-datejust-41",
    category: "fashion", subcategory: "watches", price: 49999, originalPrice: 54999,
    discount: 9, currency: "AED", rating: 4.9, reviewCount: 321, brand: "Rolex",
    inStock: true, stockCount: 3, tags: ["featured"],
    description: "Timeless elegance with Oystersteel and White Gold case.",
    specs: { Material: "Oystersteel & White Gold", Movement: "Calibre 3235", "Water Resistance": "100m" },
    deliveryDays: 5, soldBy: "Noon", expressDelivery: false
  },
  // More Home
  {
    id: "p039", title: "Philips Hue Smart Light Starter Kit", slug: "philips-hue-starter-kit",
    category: "home-kitchen", subcategory: "smart-home", price: 499, originalPrice: 649,
    discount: 23, currency: "AED", rating: 4.6, reviewCount: 1543, brand: "Philips",
    inStock: true, stockCount: 35, tags: ["featured"],
    description: "Smart color lighting kit with bridge and 3 A19 bulbs.",
    specs: { Bulbs: "3", Colors: "16 million", App: "Philips Hue", Connectivity: "Zigbee/Wi-Fi" },
    deliveryDays: 2, soldBy: "Noon", expressDelivery: true
  },
  {
    id: "p040", title: "Breville Barista Express Espresso Machine", slug: "breville-barista-express",
    category: "home-kitchen", subcategory: "kitchen-appliances", price: 2299, originalPrice: 2799,
    discount: 18, currency: "AED", rating: 4.8, reviewCount: 1876, brand: "Breville",
    inStock: true, stockCount: 18, tags: ["featured", "bestseller"],
    description: "Grind, dose, tamp, and extract espresso all in one machine.",
    specs: { Grinder: "Built-in conical burr", Pressure: "15 bar", Steam: "Micro-foam milk", Tank: "2L" },
    deliveryDays: 2, soldBy: "Noon", expressDelivery: true
  }
];

module.exports = products;
