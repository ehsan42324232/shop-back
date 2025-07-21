from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from shop.models import Store, Product, Category
from shop.storefront_models import Order, OrderItem
from shop.models_with_attributes import ProductReview


class ReviewSystemTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Create test users
        self.store_owner = User.objects.create_user(
            username='storeowner',
            email='owner@example.com',
            password='testpass123'
        )
        
        self.customer = User.objects.create_user(
            username='customer',
            email='customer@example.com',
            password='testpass123'
        )
        
        # Create test store
        self.store = Store.objects.create(
            name='Test Store',
            owner=self.store_owner,
            domain='teststore.com',
            is_active=True
        )
        
        # Create test category and product
        self.category = Category.objects.create(
            name='Test Category',
            store=self.store
        )
        
        self.product = Product.objects.create(
            name='Test Product',
            price=100000,
            store=self.store,
            category=self.category,
            is_active=True
        )
        
        # Create completed order for verified purchase
        self.order = Order.objects.create(
            customer=self.customer,
            store=self.store,
            order_number='ORD-001',
            status='delivered',
            total_amount=100000
        )
        
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            price=100000
        )

    def test_create_product_review(self):
        """Test creating a product review"""
        self.client.force_authenticate(user=self.customer)
        
        response = self.client.post(f'/api/products/{self.product.id}/reviews/', {
            'rating': 5,
            'title': 'عالی بود',
            'comment': 'محصول بسیار خوبی است',
            'pros': 'کیفیت عالی',
            'cons': 'هیچی'
        }, HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ProductReview.objects.count(), 1)
        
        review = ProductReview.objects.first()
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.verified_purchase, True)  # Has order item

    def test_get_product_reviews(self):
        """Test getting product reviews"""
        # Create a review
        review = ProductReview.objects.create(
            product=self.product,
            customer=self.customer,
            rating=4,
            title='خوب بود',
            comment='محصول خوبی است',
            status='approved'
        )
        
        response = self.client.get(f'/api/products/{self.product.id}/reviews/', 
                                   HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_review_moderation(self):
        """Test review moderation by store owner"""
        # Create pending review
        review = ProductReview.objects.create(
            product=self.product,
            customer=self.customer,
            rating=4,
            title='خوب بود',
            comment='محصول خوبی است',
            status='pending'
        )
        
        self.client.force_authenticate(user=self.store_owner)
        
        response = self.client.post(f'/api/reviews/{review.id}/moderate/', {
            'action': 'approve',
            'admin_note': 'نظر تأیید شد'
        }, HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        review.refresh_from_db()
        self.assertEqual(review.status, 'approved')

    def test_mark_review_helpful(self):
        """Test marking review as helpful"""
        review = ProductReview.objects.create(
            product=self.product,
            customer=self.customer,
            rating=4,
            title='خوب بود',
            comment='محصول خوبی است',
            status='approved'
        )
        
        # Another user marking as helpful
        other_user = User.objects.create_user(
            username='otheruser',
            password='testpass123'
        )
        
        self.client.force_authenticate(user=other_user)
        
        response = self.client.post(
            f'/api/products/{self.product.id}/reviews/{review.id}/helpful/', 
            {'is_helpful': True}, 
            HTTP_HOST='teststore.com'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['helpful_count'], 1)

    def test_review_summary(self):
        """Test getting review summary for product"""
        # Create multiple reviews
        for i in range(3):
            ProductReview.objects.create(
                product=self.product,
                customer=self.customer,
                rating=4 + (i % 2),  # Ratings 4 and 5
                title=f'نظر {i+1}',
                comment='نظر تست',
                status='approved'
            )
        
        response = self.client.get(
            f'/api/products/{self.product.id}/reviews/summary/', 
            HTTP_HOST='teststore.com'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_reviews'], 3)
        self.assertIn('average_rating', response.data)
        self.assertIn('rating_distribution', response.data)

    def test_pending_reviews_for_store_owner(self):
        """Test getting pending reviews for store owner"""
        # Create pending review
        ProductReview.objects.create(
            product=self.product,
            customer=self.customer,
            rating=4,
            title='خوب بود',
            comment='محصول خوبی است',
            status='pending'
        )
        
        self.client.force_authenticate(user=self.store_owner)
        
        response = self.client.get('/api/reviews/pending/', 
                                   HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['reviews']), 1)

    def test_bulk_moderate_reviews(self):
        """Test bulk moderation of reviews"""
        # Create multiple pending reviews
        reviews = []
        for i in range(3):
            review = ProductReview.objects.create(
                product=self.product,
                customer=self.customer,
                rating=4,
                title=f'نظر {i+1}',
                comment='نظر تست',
                status='pending'
            )
            reviews.append(review)
        
        self.client.force_authenticate(user=self.store_owner)
        
        response = self.client.post('/api/reviews/bulk-moderate/', {
            'review_ids': [r.id for r in reviews],
            'action': 'approve'
        }, HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['updated_count'], 3)

    def test_duplicate_review_prevention(self):
        """Test preventing duplicate reviews from same customer"""
        # Create first review
        ProductReview.objects.create(
            product=self.product,
            customer=self.customer,
            rating=4,
            title='اولین نظر',
            comment='نظر اول'
        )
        
        self.client.force_authenticate(user=self.customer)
        
        # Try to create second review
        response = self.client.post(f'/api/products/{self.product.id}/reviews/', {
            'rating': 5,
            'title': 'دومین نظر',
            'comment': 'نظر دوم'
        }, HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_review_stats(self):
        """Test detailed review statistics"""
        # Create reviews with different ratings
        ratings = [5, 4, 4, 3, 5]
        for rating in ratings:
            ProductReview.objects.create(
                product=self.product,
                customer=self.customer,
                rating=rating,
                title='نظر تست',
                comment='نظر تست',
                status='approved'
            )
        
        response = self.client.get(f'/api/products/{self.product.id}/reviews/stats/', 
                                   HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_reviews'], 5)
        self.assertIn('rating_distribution', response.data)
        self.assertIn('recent_reviews', response.data)