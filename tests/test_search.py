from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from shop.models import Store, Product, Category


class SearchTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Create test user and store
        self.user = User.objects.create_user(
            username='testowner',
            email='test@example.com',
            password='testpass123'
        )
        
        self.store = Store.objects.create(
            name='Test Store',
            owner=self.user,
            domain='teststore.com',
            is_active=True
        )
        
        # Create test category
        self.category = Category.objects.create(
            name='Test Category',
            store=self.store
        )
        
        # Create test products
        self.product1 = Product.objects.create(
            name='تی‌شرت قرمز',
            description='تی‌شرت زیبا با رنگ قرمز',
            price=50000,
            store=self.store,
            category=self.category,
            is_active=True
        )
        
        self.product2 = Product.objects.create(
            name='شلوار آبی',
            description='شلوار راحت با رنگ آبی',
            price=80000,
            store=self.store,
            category=self.category,
            is_active=True
        )

    def test_product_search(self):
        """Test basic product search functionality"""
        response = self.client.get('/api/search/', {
            'q': 'تی‌شرت',
        }, HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'تی‌شرت قرمز')

    def test_search_suggestions(self):
        """Test search suggestions"""
        response = self.client.get('/api/search/suggestions/', {
            'q': 'تی',
        }, HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('suggestions', response.data)

    def test_price_filter(self):
        """Test price range filtering"""
        response = self.client.get('/api/search/', {
            'min_price': '45000',
            'max_price': '60000',
        }, HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'تی‌شرت قرمز')

    def test_category_filter(self):
        """Test category filtering"""
        response = self.client.get('/api/search/', {
            'category': self.category.id,
        }, HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_sorting(self):
        """Test search result sorting"""
        response = self.client.get('/api/search/', {
            'sort': 'price',
            'order': 'asc',
        }, HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(results[0]['name'], 'تی‌شرت قرمز')  # Lower price first
        self.assertEqual(results[1]['name'], 'شلوار آبی')

    def test_faceted_search(self):
        """Test faceted search functionality"""
        response = self.client.get('/api/search/', HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('facets', response.data)
        facets = response.data['facets']
        
        self.assertIn('categories', facets)
        self.assertIn('price_ranges', facets)
        self.assertIn('availability', facets)

    def test_empty_search(self):
        """Test search with no query"""
        response = self.client.get('/api/search/', HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)  # All products

    def test_no_results_search(self):
        """Test search with no matching results"""
        response = self.client.get('/api/search/', {
            'q': 'nonexistent',
        }, HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)

    def test_search_log(self):
        """Test search logging"""
        response = self.client.post('/api/search/log/', {
            'query': 'تی‌شرت',
            'results_count': 1,
        }, HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'logged')